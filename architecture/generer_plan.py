# -*- coding: utf-8 -*-
"""
Plan d'implantation physique - Groupe 7 (surveillance d'une ligne de production).

Une seule source de vérité : les listes ZONES et EQUIPEMENTS ci-dessous.
Le script en tire :
  - plan_implantation.svg   : le plan seul (rapport Word, impression, PNG)
  - plan_implantation.html  : la page complète (plan + nomenclature + explications)
  - noeuds_cooja.csv        : les positions (en mètres) à reprendre dans Cooja

Pour déplacer un équipement : modifier ses coordonnées x, y (en mètres) puis relancer
    python generer_plan.py
"""
import csv
import math
import pathlib

ICI = pathlib.Path(__file__).resolve().parent

# 1 m sur le terrain = 20 unités de dessin ; (OX, OY) = coin nord-ouest du bâtiment
S, OX, OY = 20, 70, 150
VB_W, VB_H = 1440, 870
LARGEUR, PROFONDEUR = 50, 30          # bâtiment 50 m x 30 m = 1 500 m²
PORTEE_WIFI = 30                      # portée WiFi intérieure retenue (m)
PORTEE_COOJA = 20                     # portée radio 802.15.4 réglée dans Cooja (m)


def X(m): return OX + S * m
def Y(m): return OY + S * m
def fmt(v): return f"{v:.1f}".rstrip("0").rstrip(".")
def esc(t): return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
def cote(m): return f"{m:.2f}".replace(".", ",")
def virg(v): return fmt(v).replace(".", ",")


# --------------------------------------------------------------------------- données
ZONES = [  # code, nom complet, étiquette sur plan, x0, y0, x1, y1, famille
    ("Z1", "Accueil · entrée du personnel", "Z1 · ACCUEIL", 0, 0, 8, 8, "office"),
    ("Z2", "Salle de contrôle (supervision)", "Z2 · SALLE DE CONTRÔLE", 8, 0, 22, 8, "office"),
    ("Z3", "Local technique (réseau + serveur)", "Z3 · LOCAL TECHNIQUE", 22, 0, 30, 8, "tech"),
    ("Z4", "Vestiaires · sanitaires", "Z4 · VESTIAIRES", 30, 0, 40, 8, "neutral"),
    ("Z5", "Bureau maintenance", "Z5 · MAINTENANCE", 40, 0, 50, 8, "office"),
    ("Z6", "Réception des matières premières", "Z6 · RÉCEPTION MP", 0, 8, 10, 30, "store"),
    ("Z7", "Ligne de production (3 machines)", "Z7 · LIGNE DE PRODUCTION", 10, 8, 40, 30, "prod"),
    ("Z8", "Stock produits finis · expédition", "Z8 · EXPÉDITION", 40, 8, 50, 30, "store"),
]

MACHINES = [  # repère, procédé, x0, x1, seuil, capteur
    ("M1", "Découpe", 12, 18, "85 °C", "DS18B20"),
    ("M2", "Presse", 21, 27, "90 °C", "DS18B20"),
    ("M3", "Four", 30, 36, "220 °C", "sonde type K"),
]
MACH_Y0, MACH_Y1 = 16.5, 23.5
CONV_Y0, CONV_Y1 = 19.3, 20.7

LIPO = "Batterie LiPo 3,7 V (prototype : USB 5 V)"
SECT = "Secteur 220 V → 5 V"
EQUIPEMENTS = [
    dict(id="GW", fam="infra", x=28, y=4.5, zone="Z3", cooja=1,
         nom="Passerelle + serveur Raspberry Pi 4 (4 Go, microSD 64 Go) : Mosquitto, Node-RED, InfluxDB, Grafana",
         alim="Secteur 5 V / 3 A derrière l'onduleur", liaison="Ethernet ↔ SW",
         dest="Reçoit toutes les mesures, sert le tableau de bord, envoie les alertes"),
    dict(id="SW", fam="infra", x=23.4, y=4.5, zone="Z3", cooja=None,
         nom="Switch Ethernet 8 ports PoE", alim="Secteur via onduleur",
         liaison="Ethernet ↔ GW, AP, RTR, E2", dest="Relaie les trames entre équipements"),
    dict(id="RTR", fam="infra", x=23.4, y=2.2, zone="Z3", cooja=None,
         nom="Routeur 4G (modem USB) ou box fibre", alim="Secteur via onduleur",
         liaison="Ethernet ↔ SW · 4G/fibre → Internet", dest="Serveur SMTP Gmail, API SMS"),
    dict(id="UPS", fam="infra", x=25.3, y=6.9, zone="Z3", cooja=None,
         nom="Onduleur, autonomie ≥ 30 min", alim="Secteur 220 V",
         liaison="Alimente GW, SW, RTR, AP", dest="—"),
    dict(id="AP", fam="infra", x=23.4, y=13, zone="Z7", cooja=None,
         nom="Point d'accès WiFi 2,4 GHz fixé au plafond (h ≈ 6 m)", alim="PoE depuis SW",
         liaison="WiFi ↔ nœuds · Ethernet → SW", dest="GW (via SW)"),
    dict(id="T1", fam="temp", x=15, y=16.5, zone="Z7", cooja=2,
         nom="Nœud thermique M1 (découpe) : ESP32 + DS18B20, seuil 85 °C", alim=LIPO,
         liaison="WiFi → AP", dest="GW · factory/machines/MACHINE_01"),
    dict(id="T2", fam="temp", x=24, y=16.5, zone="Z7", cooja=3,
         nom="Nœud thermique M2 (presse) : ESP32 + DS18B20, seuil 90 °C", alim=LIPO,
         liaison="WiFi → AP", dest="GW · factory/machines/MACHINE_02"),
    dict(id="T3", fam="temp", x=33, y=16.5, zone="Z7", cooja=4,
         nom="Nœud thermique M3 (four) : ESP32 + thermocouple K (MAX6675), seuil 220 °C", alim=LIPO,
         liaison="WiFi → AP", dest="GW · factory/machines/MACHINE_03"),
    dict(id="C1", fam="count", x=19.5, y=17.6, zone="Z7", cooja=5,
         nom="Nœud de comptage sortie M1 : ESP32 + barrière IR FC-51", alim=SECT,
         liaison="WiFi → AP", dest="GW · factory/production/POSTE_01"),
    dict(id="C2", fam="count", x=28.5, y=17.6, zone="Z7", cooja=6,
         nom="Nœud de comptage sortie M2 : ESP32 + barrière IR FC-51", alim=SECT,
         liaison="WiFi → AP", dest="GW · factory/production/POSTE_02"),
    dict(id="C3", fam="count", x=37.5, y=17.6, zone="Z7", cooja=7,
         nom="Nœud de comptage sortie M3 : ESP32 + barrière IR FC-51", alim=SECT,
         liaison="WiFi → AP", dest="GW · factory/production/POSTE_03"),
    dict(id="P1", fam="pir", x=5.5, y=1.2, zone="Z1", cooja=8, vise=(0, 4),
         nom="Nœud intrusion entrée du personnel : ESP32 + PIR HC-SR501 + buzzer",
         alim="Secteur + batterie de secours", liaison="WiFi → AP · buzzer local",
         dest="GW · factory/security/ZONE_01"),
    dict(id="P2", fam="pir", x=4, y=15, zone="Z6", cooja=9, vise=(0, 20),
         nom="Nœud intrusion quai de réception : ESP32 + PIR HC-SR501 + buzzer",
         alim="Secteur + batterie de secours", liaison="WiFi → AP · buzzer local",
         dest="GW · factory/security/ZONE_02"),
    dict(id="P3", fam="pir", x=46, y=15, zone="Z8", cooja=10, vise=(50, 20),
         nom="Nœud intrusion quai d'expédition : ESP32 + PIR HC-SR501 + buzzer",
         alim="Secteur + batterie de secours", liaison="WiFi → AP · buzzer local",
         dest="GW · factory/security/ZONE_03"),
    dict(id="E1", fam="screen", x=33, y=8.4, zone="Z7", cooja=None,
         nom="Écran tactile 15″ mural, Grafana en mode kiosque", alim="Secteur",
         liaison="WiFi ← AP", dest="Affiche le tableau de bord de GW (HTTP :3000)"),
    dict(id="E2", fam="screen", x=15, y=4.5, zone="Z2", cooja=None,
         nom="Poste de supervision (PC + écran)", alim="Secteur",
         liaison="Ethernet ← SW", dest="Tableau de bord + réception des emails d'alerte"),
]
EQ = {e["id"]: e for e in EQUIPEMENTS}

# --------------------------------------------------------------------------- styles SVG
SVG_CSS = """
.plan text{font-family:var(--f-cond)}
.sheet{fill:var(--paper)}
.ttl{font-family:var(--f-disp);font-size:21px;font-weight:700;letter-spacing:.05em;fill:var(--ink)}
.sub{font-size:11.5px;fill:var(--muted)}
.lb,.lb-s,.zl,.ml,.mt,.cote,.lnk{paint-order:stroke;stroke:var(--paper);stroke-width:3px;stroke-linejoin:round}
.lb{font-size:11px;font-weight:500;fill:var(--ink)}
.lb-s{font-size:9.5px;fill:var(--muted)}
.lnk{font-size:10px;font-weight:600;fill:var(--wifi)}
.lnk-wan{fill:var(--wan)}
.lnk-eth{fill:var(--ink)}
.zl{font-size:10.5px;font-weight:600;letter-spacing:.08em;fill:var(--muted)}
.ml{font-size:11.5px;font-weight:600;fill:var(--ink);stroke:var(--mach)}
.mt{font-size:10px;fill:var(--muted);stroke:var(--mach)}
.sid{font-family:var(--f-mono);font-size:9.5px;font-weight:600;fill:var(--on-sym)}
.cote{font-family:var(--f-mono);font-size:10px;fill:var(--ink)}
.dim{stroke:var(--ink);stroke-width:.8}
.dim-ext{stroke:var(--muted);stroke-width:.6}
.wall-ext{stroke:var(--wall);stroke-width:8;stroke-linecap:square}
.wall-int{stroke:var(--wall);stroke-width:4;stroke-linecap:square}
.z-office{fill:var(--z-office)}.z-tech{fill:var(--z-tech)}.z-prod{fill:var(--z-prod)}
.z-store{fill:var(--z-store)}.z-neutral{fill:var(--z-neutral)}
.door-leaf{stroke:var(--wall);stroke-width:1.6}
.door-arc{stroke:var(--muted);stroke-width:.8;fill:none;stroke-dasharray:3 2}
.rideau{stroke:var(--wan);stroke-width:3;stroke-dasharray:6 4}
.marq{stroke:var(--mark);stroke-width:1.4;stroke-dasharray:10 6;fill:none}
.zone-sep{stroke:var(--muted);stroke-width:1;stroke-dasharray:2 4}
.mach{fill:var(--mach);stroke:var(--wall);stroke-width:1.4}
.conv{fill:var(--conv);stroke:var(--wall);stroke-width:1}
.roll{stroke:var(--wall);stroke-width:.6;opacity:.5}
.pal{fill:var(--pal);stroke:var(--wall);stroke-width:.6}
.flow{stroke:var(--ink);stroke-width:1.4;fill:none}
.cone{fill:var(--pir);fill-opacity:.13;stroke:var(--pir);stroke-opacity:.55;stroke-width:1}
.lk-wifi{stroke:var(--wifi);stroke-width:1.4;stroke-dasharray:6 4;fill:none}
.lk-eth{stroke:var(--ink);stroke-width:2.4;fill:none}
.lk-wan{stroke:var(--wan);stroke-width:2;stroke-dasharray:10 4 2 4;fill:none}
.lk-flow{stroke:var(--ink);stroke-width:1.4;fill:none}
.beam{stroke:var(--beam);stroke-width:1.6;stroke-dasharray:2 2}
.wire{stroke:var(--count);stroke-width:1}
.emit{fill:var(--count)}
.mk-wifi{fill:var(--wifi)}.mk-ink{fill:var(--ink)}.mk-wan{fill:var(--wan)}
.s-temp{fill:var(--temp)}.s-count{fill:var(--count)}.s-pir{fill:var(--pir)}
.s-infra{fill:var(--infra)}.s-screen{fill:var(--screen)}
.box{fill:var(--paper);stroke:var(--ink);stroke-width:1.2}
.box-wan{fill:var(--paper);stroke:var(--wan);stroke-width:1.4}
.bz{fill:var(--pir)}
.ct-frame{fill:var(--paper);stroke:var(--ink);stroke-width:1.2}
.ct-rule{stroke:var(--ink);stroke-width:.7}
.ct-k{font-size:8.5px;letter-spacing:.1em;fill:var(--muted)}
.ct-v{font-size:11.5px;font-weight:500;fill:var(--ink)}
.ct-h{font-family:var(--f-disp);font-size:14px;font-weight:700;letter-spacing:.05em;fill:var(--ink)}
.lgh{font-size:10px;font-weight:600;letter-spacing:.12em;fill:var(--muted)}
.lg{font-size:11px;fill:var(--ink)}
.sc-a{fill:var(--ink)}.sc-b{fill:var(--paper);stroke:var(--ink);stroke-width:.8}
"""

# Valeurs « papier » utilisées pour le fichier SVG autonome (pas de variables CSS)
TOKENS_CLAIRS = {
    "--paper": "#F6F8F9", "--ink": "#17293B", "--muted": "#5A6B7B", "--wall": "#1E2B38",
    "--z-office": "#E3EAF2", "--z-tech": "#D5EBE6", "--z-prod": "#FAF0D9", "--z-store": "#E5EEDD",
    "--z-neutral": "#ECEEF0", "--temp": "#C63F29", "--count": "#1F66AE", "--pir": "#7B3FAF",
    "--infra": "#0E746D", "--screen": "#4E5D6C", "--wifi": "#0E746D", "--wan": "#B4611A",
    "--beam": "#D93636", "--mark": "#C99A00", "--mach": "#D3DAE1", "--conv": "#B9C3CD",
    "--pal": "#E2CBA2", "--on-sym": "#FFFFFF",
    "--f-cond": "'IBM Plex Sans Condensed','Arial Narrow',Arial,sans-serif",
    "--f-disp": "'Barlow Condensed','Arial Narrow',Arial,sans-serif",
    "--f-mono": "'IBM Plex Mono',Consolas,monospace",
}

# --------------------------------------------------------------------------- primitives
svg = []


def add(s): svg.append(s)


def text(x, y, s, cls="lb", anchor="start", rot=None):
    tr = f' transform="rotate({fmt(rot)} {fmt(x)} {fmt(y)})"' if rot is not None else ""
    add(f'<text x="{fmt(x)}" y="{fmt(y)}" class="{cls}" text-anchor="{anchor}"{tr}>{esc(s)}</text>')


def line(x1, y1, x2, y2, cls, extra=""):
    add(f'<line x1="{fmt(x1)}" y1="{fmt(y1)}" x2="{fmt(x2)}" y2="{fmt(y2)}" class="{cls}"{extra}/>')


def rect(x, y, w, h, cls, rx=0, extra=""):
    r = f' rx="{fmt(rx)}"' if rx else ""
    add(f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}"{r} class="{cls}"{extra}/>')


def wall(a, b, cls):
    line(X(a[0]), Y(a[1]), X(b[0]), Y(b[1]), cls)


# Gabarit de chaque symbole : demi-largeur / demi-hauteur ou rayon (unités de dessin)
def symbole(fam, px, py, label):
    if fam == "temp":
        add(f'<circle cx="{fmt(px)}" cy="{fmt(py)}" r="11" class="s-temp"/>')
    elif fam == "count":
        rect(px - 11, py - 11, 22, 22, "s-count", rx=2)
    elif fam == "pir":
        add(f'<polygon points="{fmt(px)},{fmt(py-13)} {fmt(px+13)},{fmt(py)} {fmt(px)},{fmt(py+13)} {fmt(px-13)},{fmt(py)}" class="s-pir"/>')
    elif fam == "infra":
        rect(px - 18, py - 10, 36, 20, "s-infra", rx=3)
    elif fam == "screen":
        rect(px - 20, py - 7, 40, 14, "s-screen", rx=2)
    text(px, py + 3.4, label, "sid", "middle")


def bord(fam, ux, uy):
    """Distance du centre au bord du symbole dans la direction (ux, uy) unitaire."""
    ax, ay = abs(ux) or 1e-9, abs(uy) or 1e-9
    if fam == "temp":
        return 13
    if fam == "pir":
        return 15 / (ax + ay)
    hw, hh = {"count": (13, 13), "infra": (20, 12), "screen": (22, 9)}[fam]
    return min(hw / ax, hh / ay)


def liaison(a, b, cls, marker=None):
    """Trait entre deux équipements, raccourci aux bords des symboles."""
    ea, eb = EQ[a], EQ[b]
    x1, y1, x2, y2 = X(ea["x"]), Y(ea["y"]), X(eb["x"]), Y(eb["y"])
    d = math.hypot(x2 - x1, y2 - y1)
    ux, uy = (x2 - x1) / d, (y2 - y1) / d
    da, db = bord(ea["fam"], ux, uy), bord(eb["fam"], ux, uy) + (2 if marker else 0)
    m = f' marker-end="url(#{marker})"' if marker else ""
    line(x1 + ux * da, y1 + uy * da, x2 - ux * db, y2 - uy * db, cls, m)


def porte(charniere, ouvert, ferme):
    """Porte battante façon plan d'architecte : vantail ouvert + arc de débattement."""
    hx, hy = X(charniere[0]), Y(charniere[1])
    ox, oy = X(ouvert[0]), Y(ouvert[1])
    fx, fy = X(ferme[0]), Y(ferme[1])
    r = math.hypot(ox - hx, oy - hy)
    cross = (ox - hx) * (fy - hy) - (oy - hy) * (fx - hx)
    line(hx, hy, ox, oy, "door-leaf")
    add(f'<path d="M{fmt(ox)},{fmt(oy)} A{fmt(r)},{fmt(r)} 0 0 {1 if cross > 0 else 0} {fmt(fx)},{fmt(fy)}" class="door-arc"/>')


def tick(px, py):
    line(px - 4, py + 4, px + 4, py - 4, "dim")


def chaine_h(y, xs, depuis):
    line(X(xs[0]) - 6, y, X(xs[-1]) + 6, y, "dim")
    for xm in xs:
        line(X(xm), depuis, X(xm), y + (-6 if depuis > y else 6), "dim-ext")
        tick(X(xm), y)
    for a, b in zip(xs, xs[1:]):
        text((X(a) + X(b)) / 2, y - 5, cote(b - a) + (" m" if len(xs) == 2 else ""), "cote", "middle")


def chaine_v(x, ys, depuis, cote_gauche=True):
    line(x, Y(ys[0]) - 6, x, Y(ys[-1]) + 6, "dim")
    for ym in ys:
        line(depuis, Y(ym), x + (6 if depuis > x else -6), Y(ym), "dim-ext")
        tick(x, Y(ym))
    for a, b in zip(ys, ys[1:]):
        mid = (Y(a) + Y(b)) / 2
        lab = cote(b - a) + (" m" if len(ys) == 2 else "")
        if cote_gauche:
            text(x - 5, mid, lab, "cote", "middle", rot=-90)
        else:
            text(x + 5, mid, lab, "cote", "middle", rot=90)


# --------------------------------------------------------------------------- dessin
def dessiner():
    add('<defs>')
    for mid, cls in (("mk-wifi", "mk-wifi"), ("mk-ink", "mk-ink"), ("mk-wan", "mk-wan")):
        add(f'<marker id="{mid}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" '
            f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" class="{cls}"/></marker>')
    for code, _, _, x0, y0, x1, y1, _ in ZONES:
        add(f'<clipPath id="clip-{code}"><rect x="{fmt(X(x0)+2)}" y="{fmt(Y(y0)+2)}" '
            f'width="{fmt(S*(x1-x0)-4)}" height="{fmt(S*(y1-y0)-4)}"/></clipPath>')
    add('</defs>')
    rect(0, 0, VB_W, VB_H, "sheet")

    # En-tête du plan
    text(OX, 44, "PLAN D'IMPLANTATION · RDC", "ttl")
    text(OX, 64, "Usine · 50 × 30 m (1 500 m²) · système IoT de surveillance", "sub")

    # Zones (sols)
    for code, _, lab, x0, y0, x1, y1, fam in ZONES:
        rect(X(x0), Y(y0), S * (x1 - x0), S * (y1 - y0), f"z-{fam}")

    # Marquages au sol : limites de zones dans le hall + allée piétonne
    line(X(10), Y(8), X(10), Y(30), "zone-sep")
    line(X(40), Y(8), X(40), Y(30), "zone-sep")
    line(X(0.6), Y(26.3), X(49.4), Y(26.3), "marq")
    line(X(0.6), Y(28.7), X(49.4), Y(28.7), "marq")
    text(X(25), Y(27.75), "ALLÉE PIÉTONNE", "lb-s", "middle")

    # Palettes (1,2 x 1,0 m) en réception et en expédition
    for x0, lab in ((1.0, "palettes matières premières"), (41.0, "palettes produits finis")):
        for row in (10.0, 11.6):
            for k in range(4):
                rect(X(x0 + k * 2.0), Y(row), 1.2 * S, 1.0 * S, "pal")
        text(X(x0 + 3.6), Y(13.4), lab, "lb-s", "middle")

    # Convoyeur à rouleaux + machines posées dessus
    rect(X(10.5), Y(CONV_Y0), S * 29, S * (CONV_Y1 - CONV_Y0), "conv")
    k = 10.75
    while k < 39.5:
        line(X(k), Y(CONV_Y0) + 1, X(k), Y(CONV_Y1) - 1, "roll")
        k += 0.5
    for rid, proc, x0, x1, seuil, capteur in MACHINES:
        rect(X(x0), Y(MACH_Y0), S * (x1 - x0), S * (MACH_Y1 - MACH_Y0), "mach", rx=2)
        cx = X((x0 + x1) / 2)
        text(cx, Y(17.75), f"{rid} · {proc}", "ml", "middle")
        text(cx, Y(18.55), capteur, "mt", "middle")
        text(cx, Y(21.9), f"seuil {seuil}", "ml", "middle")
    line(X(11), Y(24.9), X(39), Y(24.9), "flow", ' marker-end="url(#mk-ink)"')
    text(X(25), Y(24.4), "sens du flux produit : réception → M1 → M2 → M3 → expédition", "lb-s", "middle")

    # Cônes de détection PIR : 7 m, 120°, coupés par les murs de leur zone
    for e in EQUIPEMENTS:
        if e["fam"] != "pir":
            continue
        cx, cy = X(e["x"]), Y(e["y"])
        a = math.atan2(e["vise"][1] - e["y"], e["vise"][0] - e["x"])
        r = 7 * S
        p1 = (cx + r * math.cos(a - math.pi / 3), cy + r * math.sin(a - math.pi / 3))
        p2 = (cx + r * math.cos(a + math.pi / 3), cy + r * math.sin(a + math.pi / 3))
        add(f'<path d="M{fmt(cx)},{fmt(cy)} L{fmt(p1[0])},{fmt(p1[1])} A{fmt(r)},{fmt(r)} 0 0 1 '
            f'{fmt(p2[0])},{fmt(p2[1])} Z" class="cone" clip-path="url(#clip-{e["zone"]})"/>')

    # Murs extérieurs (0,40 m) avec ouvertures
    for a, b in (((0, 0), (50, 0)), ((50, 0), (50, 17)), ((50, 23), (50, 30)), ((50, 30), (0, 30)),
                 ((0, 30), (0, 23)), ((0, 17), (0, 5)), ((0, 3), (0, 0))):
        wall(a, b, "wall-ext")
    # Cloisons (0,20 m) avec passages de portes
    for a, b in (((0, 8), (6.5, 8)), ((7.7, 8), (20, 8)), ((21.2, 8), (37, 8)), ((38.2, 8), (47.5, 8)),
                 ((48.7, 8), (50, 8)), ((8, 0), (8, 5.5)), ((8, 6.7), (8, 8)),
                 ((22, 0), (22, 5.5)), ((22, 6.7), (22, 8)), ((30, 0), (30, 8)), ((40, 0), (40, 8))):
        wall(a, b, "wall-int")
    # Portes battantes
    porte((0, 3), (1, 3), (0, 4))
    porte((0, 5), (1, 5), (0, 4))
    for xa in (6.5, 20, 37, 47.5):
        porte((xa, 8), (xa, 9.2), (xa + 1.2, 8))
    porte((8, 5.5), (9.2, 5.5), (8, 6.7))
    porte((22, 5.5), (23.2, 5.5), (22, 6.7))
    # Portes sectionnelles des quais (6 m)
    line(X(0), Y(17), X(0), Y(23), "rideau")
    line(X(50), Y(17), X(50), Y(23), "rideau")
    text(X(0) - 12, Y(4), "Entrée personnel", "lb-s", "middle", rot=-90)
    text(X(0) - 12, Y(20), "Quai réception · porte sectionnelle 6 m", "lb-s", "middle", rot=-90)
    text(X(50) + 12, Y(20), "Quai expédition · porte sectionnelle 6 m", "lb-s", "middle", rot=90)

    # Étiquettes de zones
    for code, _, lab, x0, y0, *_ in ZONES:
        text(X(x0) + 7, Y(y0) + 17, lab, "zl")

    # ---- Liaisons (sous les symboles)
    # Radio WiFi : chaque nœud capteur parle uniquement au point d'accès
    for e in EQUIPEMENTS:
        if e["fam"] in ("temp", "count", "pir"):
            liaison(e["id"], "AP", "lk-wifi", "mk-wifi")
    liaison("AP", "E1", "lk-wifi", "mk-wifi")
    # Câbles Ethernet
    for a, b in (("AP", "SW"), ("SW", "RTR"), ("SW", "GW"), ("SW", "E2")):
        liaison(a, b, "lk-eth")
    # Barrières IR des postes de comptage
    for e in EQUIPEMENTS:
        if e["fam"] == "count":
            px = X(e["x"])
            line(px, Y(e["y"]) + 11, px, Y(CONV_Y0) - 4, "wire")
            rect(px - 4, Y(CONV_Y0) - 5, 8, 4, "emit")
            rect(px - 4, Y(CONV_Y1) + 1, 8, 4, "emit")
            line(px, Y(CONV_Y0) - 1, px, Y(CONV_Y1) + 1, "beam")
    # Sortie Internet
    rx = X(EQ["RTR"]["x"])
    line(rx, Y(EQ["RTR"]["y"]) - 12, rx, 80, "lk-wan", ' marker-end="url(#mk-wan)"')

    # Libellés de liaisons
    p3, ap = EQ["P3"], EQ["AP"]
    mx, my = (X(p3["x"]) + X(ap["x"])) / 2, (Y(p3["y"]) + Y(ap["y"])) / 2
    ang = math.degrees(math.atan2(Y(p3["y"]) - Y(ap["y"]), X(p3["x"]) - X(ap["x"])))
    text(mx + 40, my - 3, "WiFi 2,4 GHz · MQTT vers AP", "lnk", "middle", rot=ang)
    text(X(ap["x"]) - 7, Y(10.6), "Ethernet Cat6 (PoE)", "lnk lnk-eth", "middle", rot=-90)
    text(rx + 8, 100, "WAN 4G / fibre", "lnk lnk-wan")

    # ---- Symboles
    for e in EQUIPEMENTS:
        symbole(e["fam"], X(e["x"]), Y(e["y"]), e["id"])
    # Buzzers locaux à côté des PIR
    for pid, dx in (("P1", 21), ("P2", 21), ("P3", -21)):
        bx, by = X(EQ[pid]["x"]) + dx, Y(EQ[pid]["y"])
        rect(bx - 4, by - 3, 3.5, 6, "bz")
        add(f'<polygon points="{fmt(bx-0.5)},{fmt(by-3)} {fmt(bx+4)},{fmt(by-6)} {fmt(bx+4)},{fmt(by+6)} {fmt(bx-0.5)},{fmt(by+3)}" class="bz"/>')

    # Libellés des équipements uniques
    def lab(eid, dx, dy, s, anchor="start", cls="lb"):
        text(X(EQ[eid]["x"]) + dx, Y(EQ[eid]["y"]) + dy, s, cls, anchor)
    lab("RTR", 22, 4, "Routeur 4G / fibre")
    lab("SW", 22, 4, "Switch")
    lab("GW", 0, 24, "Passerelle", "middle")
    lab("GW", 0, 36, "Raspberry Pi 4", "middle", "lb-s")
    lab("UPS", 22, 4, "Onduleur")
    lab("AP", 24, -4, "Point d'accès WiFi")
    lab("AP", 24, 8, "plafond, h ≈ 6 m", cls="lb-s")
    lab("E1", 0, 21, "Écran 15″ kiosque", "middle")
    lab("E2", 0, -13, "Poste de supervision", "middle")

    # ---- Monde extérieur : Internet → services → smartphone
    rect(rx - 75, 22, 150, 56, "box-wan", rx=28)
    text(rx, 46, "Internet", "lb", "middle")
    text(rx, 62, "4G · fibre optique", "lb-s", "middle")
    rect(690, 22, 220, 56, "box", rx=4)
    text(800, 46, "Services en ligne", "lb", "middle")
    text(800, 62, "SMTP Gmail · API SMS Orange / MTN", "lb-s", "middle")
    rect(985, 22, 140, 56, "box", rx=4)
    text(1055, 46, "Smartphone", "lb", "middle")
    text(1055, 62, "du responsable", "lb-s", "middle")
    line(rx + 75, 50, 688, 50, "lk-flow", ' marker-end="url(#mk-ink)"')
    text((rx + 75 + 688) / 2, 44, "alerte", "lb-s", "middle")
    line(910, 50, 983, 50, "lk-flow", ' marker-end="url(#mk-ink)"')
    text(947, 44, "email · SMS", "lb-s", "middle")

    # ---- Cotes
    chaine_h(128, [0, 8, 22, 30, 40, 50], Y(0) - 6)
    chaine_h(772, [0, 10, 40, 50], Y(30) + 6)
    chaine_h(800, [0, 50], Y(30) + 6)
    chaine_v(30, [0, 30], X(0) - 30)
    chaine_v(1100, [0, 8, 30], X(50) + 6, cote_gauche=False)

    # ---- Échelle graphique + nord
    for i in range(4):
        rect(OX + i * 5 * S, 826, 5 * S, 6, "sc-a" if i % 2 == 0 else "sc-b")
    for i, v in enumerate(("0", "5", "10", "15", "20 m")):
        text(OX + i * 5 * S, 848, v, "cote", "middle")
    text(OX + 20 * S + 20, 833, "Échelle graphique · 1 m = 20 unités", "lb-s")
    nx, ny = 760, 838
    add(f'<polygon points="{nx},{ny-24} {nx+8},{ny} {nx},{ny-6} {nx-8},{ny}" class="sc-a"/>')
    text(nx, ny + 14, "N", "lb", "middle")

    # ---- Légende
    lx, ly = 1140, 160
    text(lx, ly, "ÉQUIPEMENTS", "lgh")
    rows = [("temp", "T", "Nœud thermique · ESP32 + sonde (×3)"),
            ("count", "C", "Nœud de comptage · barrière IR (×3)"),
            ("pir", "P", "Nœud intrusion · PIR + buzzer (×3)"),
            ("infra", "GW", "Réseau, passerelle, alimentation"),
            ("screen", "E", "Affichage du tableau de bord")]
    for i, (fam, sid, s) in enumerate(rows):
        yy = ly + 26 + i * 25
        symbole(fam, lx + 20, yy, sid)
        text(lx + 46, yy + 4, s, "lg")
    ly2 = ly + 26 + 5 * 25 + 8
    text(lx, ly2, "LIAISONS", "lgh")
    lrows = [("lk-wifi", "Radio WiFi 2,4 GHz · MQTT"), ("lk-eth", "Câble Ethernet Cat6"),
             ("lk-wan", "Sortie Internet (4G / fibre)"), ("beam", "Faisceau IR de comptage"),
             ("door-arc", "Débattement de porte")]
    for i, (cls, s) in enumerate(lrows):
        yy = ly2 + 22 + i * 22
        line(lx + 2, yy, lx + 38, yy, cls)
        text(lx + 46, yy + 4, s, "lg")
    yy = ly2 + 22 + 5 * 22
    add(f'<path d="M{lx+4},{yy+7} L{lx+20},{yy-7} L{lx+36},{yy+7} Z" class="cone"/>')
    text(lx + 46, yy + 4, "Champ PIR · 7 m, 120°", "lg")
    ly3 = yy + 30
    text(lx, ly3, "ZONES", "lgh")
    zrows = [("z-office", "Bureaux"), ("z-tech", "Technique"), ("z-prod", "Production"),
             ("z-store", "Stockage"), ("z-neutral", "Annexes")]
    for i, (cls, s) in enumerate(zrows):
        cx_ = lx + (i % 3) * 95
        cy_ = ly3 + 14 + (i // 3) * 22
        rect(cx_, cy_ - 1, 22, 14, cls, extra=' stroke="currentColor" stroke-opacity=".25"')
        text(cx_ + 28, cy_ + 10, s, "lg")

    # ---- Cartouche
    cx0, cy0, cw = 1140, 640, 285
    rect(cx0, cy0, cw, 210, "ct-frame")
    text(cx0 + 10, cy0 + 22, "IFRI · RÉSEAUX DE CAPTEURS & IOT", "ct-h")
    line(cx0, cy0 + 34, cx0 + cw, cy0 + 34, "ct-rule")
    text(cx0 + 10, cy0 + 48, "PROJET", "ct-k")
    text(cx0 + 10, cy0 + 63, "Surveillance d'une ligne de production", "ct-v")
    line(cx0, cy0 + 74, cx0 + cw, cy0 + 74, "ct-rule")
    text(cx0 + 10, cy0 + 88, "PLANCHE", "ct-k")
    text(cx0 + 10, cy0 + 103, "Implantation physique des équipements", "ct-v")
    line(cx0, cy0 + 114, cx0 + cw, cy0 + 114, "ct-rule")
    cells = [("ÉCHELLE", "graphique"), ("DATE", "19/10/2026"), ("INDICE", "A")]
    for i, (k_, v) in enumerate(cells):
        x_ = cx0 + i * 95
        if i:
            line(x_, cy0 + 114, x_, cy0 + 162, "ct-rule")
        text(x_ + 10, cy0 + 130, k_, "ct-k")
        text(x_ + 10, cy0 + 150, v, "ct-v")
    line(cx0, cy0 + 162, cx0 + cw, cy0 + 162, "ct-rule")
    cells = [("DESSINÉ PAR", "Groupe 7"), ("NIVEAU", "RDC"), ("PLANCHE", "01 / 01")]
    for i, (k_, v) in enumerate(cells):
        x_ = cx0 + i * 95
        if i:
            line(x_, cy0 + 162, x_, cy0 + 210, "ct-rule")
        text(x_ + 10, cy0 + 178, k_, "ct-k")
        text(x_ + 10, cy0 + 198, v, "ct-v")


# --------------------------------------------------------------------------- tableaux HTML
def nomenclature_html():
    zones = {z[0]: z[1] for z in ZONES}
    rows = []
    for e in EQUIPEMENTS:
        cj = str(e["cooja"]) if e["cooja"] else "—"
        rows.append(
            f'<tr><td><span class="tag tag-{e["fam"]}">{e["id"]}</span></td><td>{esc(e["nom"])}</td>'
            f'<td>{e["zone"]} · {esc(zones[e["zone"]])}</td>'
            f'<td class="num">{virg(e["x"])} ; {virg(e["y"])}</td><td>{esc(e["alim"])}</td>'
            f'<td>{esc(e["liaison"])}</td><td>{esc(e["dest"])}</td><td class="num">{cj}</td></tr>')
    return "\n".join(rows)


def distances_html():
    ap, gw = EQ["AP"], EQ["GW"]
    rows = []
    for e in EQUIPEMENTS:
        if not e["cooja"] or e["id"] == "GW":
            continue
        d_ap = math.hypot(e["x"] - ap["x"], e["y"] - ap["y"])
        d_gw = math.hypot(e["x"] - gw["x"], e["y"] - gw["y"])
        direct = d_gw <= PORTEE_COOJA
        rows.append(
            f'<tr><td><span class="tag tag-{e["fam"]}">{e["id"]}</span></td><td class="num">{e["cooja"]}</td>'
            f'<td class="num">{virg(round(d_ap, 1))} m</td><td class="num">{virg(round(d_gw, 1))} m</td>'
            f'<td>{"direct" if direct else "<strong>relais par un voisin</strong>"}</td></tr>')
    return "\n".join(rows)


def svg_document(inline):
    corps = "\n".join(svg)
    aria = ("Plan d'implantation de l'usine : 8 zones, 3 machines sur un convoyeur, 9 nœuds capteurs "
            "reliés par WiFi à un point d'accès central, lui-même câblé à la passerelle du local technique.")
    if inline:
        return (f'<svg class="plan" viewBox="0 0 {VB_W} {VB_H}" role="img" aria-label="{aria}" '
                f'xmlns="http://www.w3.org/2000/svg">\n{corps}\n</svg>')
    css = SVG_CSS
    for k in sorted(TOKENS_CLAIRS, key=len, reverse=True):
        css = css.replace(f"var({k})", TOKENS_CLAIRS[k])
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<svg class="plan" viewBox="0 0 {VB_W} {VB_H}" '
            f'width="{VB_W}" height="{VB_H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{aria}">\n'
            f'<style>{css}</style>\n{corps}\n</svg>\n')


def main():
    dessiner()
    (ICI / "plan_implantation.svg").write_text(svg_document(inline=False), encoding="utf-8")

    modele = (ICI / "page_modele.html").read_text(encoding="utf-8")
    page = (modele.replace("{{SVG_CSS}}", SVG_CSS)
                  .replace("{{PLAN_SVG}}", svg_document(inline=True))
                  .replace("{{NOMENCLATURE}}", nomenclature_html())
                  .replace("{{DISTANCES}}", distances_html())
                  .replace("{{PORTEE_COOJA}}", str(PORTEE_COOJA)))
    (ICI / "plan_implantation.html").write_text(page, encoding="utf-8")

    with open(ICI / "noeuds_cooja.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["id_cooja", "repere", "famille", "x_m", "y_m", "zone"])
        for e in sorted((e for e in EQUIPEMENTS if e["cooja"]), key=lambda e: e["cooja"]):
            w.writerow([e["cooja"], e["id"], e["fam"], e["x"], e["y"], e["zone"]])
    print("OK : plan_implantation.svg, plan_implantation.html, noeuds_cooja.csv")


if __name__ == "__main__":
    main()
