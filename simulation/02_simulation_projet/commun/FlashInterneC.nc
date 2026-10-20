/*
 * MODULE FlashInterneC : lire / écrire quelques octets dans la mémoire FLASH
 * interne du microcontrôleur MSP430 (segment « information », 2 × 128 octets).
 * Contrairement à la RAM, la flash garde son contenu quand la carte redémarre :
 * c'est là que le nœud de comptage range son compteur de pièces.
 *
 * Repris de tos/lib/net/Deluge/extra/msp430/InternalFlashC.nc (Jonathan Hui, UC Berkeley,
 * licence BSD TinyOS). Principe : la flash doit être effacée avant d'être réécrite, et
 * on ne peut effacer que des segments entiers ; on alterne donc entre deux segments
 * (A et B) et un numéro de version (dernier octet) indique le plus récent.
 * Adresses valides : 0 à 126 (relatives au début du segment).
 */
module FlashInterneC {
  provides interface InternalFlash;
}
implementation {
  enum {
    IFLASH_OFFSET         = 0x1000,
    IFLASH_SIZE           = 128,
    IFLASH_SEG0_VNUM_ADDR = 0x107f,
    IFLASH_SEG1_VNUM_ADDR = 0x10ff,
    IFLASH_INVALID_VNUM   = -1,
  };

  uint8_t chooseSegment() {
    int8_t vnum0 = *(int8_t *)IFLASH_SEG0_VNUM_ADDR;
    int8_t vnum1 = *(int8_t *)IFLASH_SEG1_VNUM_ADDR;
    if (vnum0 == IFLASH_INVALID_VNUM) return 1;
    else if (vnum1 == IFLASH_INVALID_VNUM) return 0;
    return ((int8_t)(vnum0 - vnum1) < 0);
  }

  command error_t InternalFlash.write(void *addr, void *buf, uint16_t size) {
    volatile int8_t *newPtr;
    int8_t *oldPtr;
    int8_t *bufPtr = (int8_t *)buf;
    int8_t version;
    uint16_t i;

    addr += IFLASH_OFFSET;
    newPtr = oldPtr = (int8_t *)IFLASH_OFFSET;
    if (chooseSegment()) {
      oldPtr += IFLASH_SIZE;
    } else {
      addr += IFLASH_SIZE;
      newPtr += IFLASH_SIZE;
    }

    /* IMPORTANT : pendant l'effacement et l'écriture, le contrôleur de flash bloque le CPU.
       Une interruption à ce moment fait planter le MSP430 (mspsim le reproduit :
       « Got interrupt while flash controller blocks CPU »). Le module d'origine servait
       au chargeur d'amorçage, sans interruptions ; ici on les MASQUE avec atomic. */
    atomic {
      FCTL2 = FWKEY + FSSEL1 + FN2;     /* horloge du contrôleur de flash */
      FCTL3 = FWKEY;                    /* déverrouillage */
      FCTL1 = FWKEY + ERASE;            /* effacement du segment de destination */
      *newPtr = 0;
      FCTL1 = FWKEY + WRT;              /* mode écriture */
      for (i = 0; i < IFLASH_SIZE - 1; i++, newPtr++, oldPtr++) {
        if ((uint16_t)newPtr < (uint16_t)addr || (uint16_t)addr + size <= (uint16_t)newPtr)
          *newPtr = *oldPtr;            /* recopie de l'ancien contenu */
        else
          *newPtr = *bufPtr++;          /* nouveaux octets */
      }
      version = *oldPtr + 1;
      if (version == IFLASH_INVALID_VNUM) version++;
      *newPtr = version;
      FCTL1 = FWKEY;
      FCTL3 = FWKEY + LOCK;             /* reverrouillage */
    }
    return SUCCESS;
  }

  command error_t InternalFlash.read(void *addr, void *buf, uint16_t size) {
    addr += IFLASH_OFFSET;
    if (chooseSegment()) addr += IFLASH_SIZE;
    memcpy(buf, addr, size);
    return SUCCESS;
  }
}
