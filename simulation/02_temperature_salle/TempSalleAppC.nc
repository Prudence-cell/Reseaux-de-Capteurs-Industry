configuration TempSalleAppC {}
implementation {
  components MainC,  PlatformSerialC;
  components TempSalleC as App ;
  components new TimerMilliC() as Minuterie;

  App.Boot         -> MainC;
  App.Minuterie    -> Minuterie;
  App.SerieControl -> PlatformSerialC;
  App.UartByte     -> PlatformSerialC;
}
