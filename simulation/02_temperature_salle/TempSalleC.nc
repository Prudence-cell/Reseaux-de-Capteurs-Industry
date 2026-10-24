module TempSalleC {
  uses {
    interface Boot;
    interface Timer<TMilli> as Minuterie;
    interface StdControl as SerieControl;
    interface UartByte;
  }
}
implementation {
  uint16_t numero = 0;
  uint16_t temp = 250;  
  void ecrire(const char *s) { while (*s) call UartByte.send(*s++); }
  void ecrireNombre(uint16_t n) {
    char c[6]; uint8_t i = 0;
    do { c[i++] = '0' + n % 10; n /= 10; } while (n > 0);
    while (i > 0) call UartByte.send(c[--i]);
  }

  event void Boot.booted() {
    call SerieControl.start();
    call Minuterie.startPeriodic(5000);   
  }

  event void Minuterie.fired() {
    numero++;
    /* 5. Affichage du numéro de mesure et de la température */
    ecrire("Mesure ");  ecrireNombre(numero);
    ecrire(" : ");      ecrireNombre(temp / 10);
    ecrire(".");        ecrireNombre(temp % 10);
    ecrire(" C\n");
    temp += 5;         
  }
}
