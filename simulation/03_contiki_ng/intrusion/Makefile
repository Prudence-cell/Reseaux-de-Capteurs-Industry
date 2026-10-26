# Programme Contiki-NG « intrusion » pour Cooja mote (make TARGET=cooja)
CONTIKI_PROJECT = intrusion
all: $(CONTIKI_PROJECT)

PROJECTDIRS += ../commun                  # usine.h, plan.h, publication.c, conf-commune.h
PROJECT_SOURCEFILES += publication.c   # le service commun d'envoi

CONTIKI ?= $(HOME)/contiki-ng
include $(CONTIKI)/Makefile.include
