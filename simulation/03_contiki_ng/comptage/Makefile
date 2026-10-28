# Programme Contiki-NG « comptage » pour Cooja mote (make TARGET=cooja)
CONTIKI_PROJECT = comptage
all: $(CONTIKI_PROJECT)

PROJECTDIRS += ../commun                  # usine.h, plan.h, publication.c, conf-commune.h
PROJECT_SOURCEFILES += publication.c   # le service commun d'envoi

CONTIKI ?= $(HOME)/contiki-ng
include $(CONTIKI)/Makefile.include
