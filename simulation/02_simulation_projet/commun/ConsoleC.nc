/*
 * CONFIGURATION ConsoleC : relie le module ConsoleP au port série de la carte.
 * Les applications écrivent simplement « components ConsoleC; App.Console -> ConsoleC; ».
 */
configuration ConsoleC {
  provides interface Console;
}
implementation {
  components ConsoleP, PlatformSerialC;
  Console = ConsoleP;
  ConsoleP.SerieControl -> PlatformSerialC;
  ConsoleP.UartByte     -> PlatformSerialC;   /* envoi octet par octet (texte brut) */
  ConsoleP.UartStream   -> PlatformSerialC;   /* réception des commandes */
}
