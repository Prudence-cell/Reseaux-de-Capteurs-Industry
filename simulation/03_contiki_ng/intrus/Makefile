# Nœud INTRUS du test ENF6 : le programme thermique compilé avec une AUTRE clé,
# et qui ignore la vérification des acquittements (il émet quand même).
CONTIKI_PROJECT = intrus
all: $(CONTIKI_PROJECT)

PROJECTDIRS += ../commun
PROJECT_SOURCEFILES += publication.c
CFLAGS += -DCLE_RESEAU=0x0BADC0DEUL -DINTRUS

CONTIKI ?= $(HOME)/contiki-ng
include $(CONTIKI)/Makefile.include
