# -*- coding: utf-8 -*-
"""
Plan d'implantation au format DXF, à ouvrir et retoucher dans LibreCAD.

Les données (zones, machines, équipements) viennent de generer_plan.py : une seule source
de vérité pour le SVG, la page HTML, le CSV Cooja et ce DXF.

Le dessin est en vraie grandeur : 1 unité = 1 mètre, origine au coin sud-ouest du bâtiment,
axe Y vers le nord (convention DAO). Chaque famille d'objets est sur son propre calque
(murs, portes, capteurs, liaisons radio, cotes...), ce qui permet de masquer ou verrouiller
une couche dans LibreCAD (panneau « Liste des calques »).

    python generer_dxf.py   →   plan_implantation.dxf

Format DXF R12 (AC1009) : le plus simple et le mieux relu par LibreCAD.
"""
import math

import generer_plan as gp

ZMAX = gp.PROFONDEUR       # 30 m : sert à retourner l'axe Y (plan → DXF)
S = gp.S


def m(x, y):
    """Coordonnées plan (m, Y vers le sud) → DXF (m, Y vers le nord)."""
    return (x, ZMAX - y)


def u(px, py):
    """Coordonnées de dessin SVG (cartouche, légende, en-tête) → DXF (m)."""
    return ((px - gp.OX) / S, ZMAX - (py - gp.OY) / S)


def H(fs):
    """Taille de police SVG (px) → hauteur de texte DXF (m)."""
    return fs * 0.7 / S


# --------------------------------------------------------------------------- couleurs
# nom : (couleur AutoCAD ACI de repli, couleur vraie 0xRRGGBB ou None = suit le fond)
COUL = {
    "encre": (7, None), "gris": (8, 0x5A6B7B), "blanc": (7, 0xFFFFFF),
    "z-office": (254, 0xE3EAF2), "z-tech": (254, 0xD5EBE6), "z-prod": (51, 0xFAF0D9),
    "z-store": (254, 0xE5EEDD), "z-neutral": (254, 0xECEEF0),
    "temp": (1, 0xC63F29), "count": (5, 0x1F66AE), "pir": (6, 0x7B3FAF),
    "pir-clair": (6, 0xE4DAEF), "infra": (130, 0x0E746D), "screen": (8, 0x4E5D6C),
    "wifi": (130, 0x0E746D), "wan": (30, 0xB4611A), "beam": (1, 0xD93636),
    "mark": (40, 0xC99A00), "mach": (254, 0xD3DAE1), "conv": (9, 0xB9C3CD),
    "pal": (41, 0xE2CBA2),
}

# nom, couleur, type de ligne, épaisseur (1/100 mm)
CALQUES = [
    ("0", "encre", "CONTINUOUS", 25),
    ("ZONES_FOND", "gris", "CONTINUOUS", 13),
    ("ZONES_NOMS", "gris", "CONTINUOUS", 18),
    ("LIMITES_ZONES", "gris", "DOT2", 13),
    ("MARQUAGE_SOL", "mark", "DASHEDX2", 25),
    ("MURS", "encre", "CONTINUOUS", 50),
    ("CLOISONS", "encre", "CONTINUOUS", 35),
    ("PORTES", "encre", "CONTINUOUS", 18),
    ("QUAIS", "wan", "DASHED", 50),
    ("MOBILIER", "gris", "CONTINUOUS", 13),
    ("CONVOYEUR", "gris", "CONTINUOUS", 18),
    ("MACHINES", "encre", "CONTINUOUS", 25),
    ("CHAMP_PIR", "pir", "CONTINUOUS", 13),
    ("CAPTEURS_THERMIQUES", "temp", "CONTINUOUS", 25),
    ("CAPTEURS_COMPTAGE", "count", "CONTINUOUS", 25),
    ("CAPTEURS_INTRUSION", "pir", "CONTINUOUS", 25),
    ("RESEAU", "infra", "CONTINUOUS", 25),
    ("AFFICHAGE", "screen", "CONTINUOUS", 25),
    ("LIAISON_WIFI", "wifi", "DASHED", 25),
    ("LIAISON_ETHERNET", "encre", "CONTINUOUS", 50),
    ("LIAISON_WAN", "wan", "DASHDOT", 35),
    ("FAISCEAU_IR", "beam", "DOT", 25),
    ("TEXTES", "encre", "CONTINUOUS", 18),
    ("COTES", "encre", "CONTINUOUS", 13),
    ("EXTERIEUR", "encre", "CONTINUOUS", 25),
    ("LEGENDE", "encre", "CONTINUOUS", 18),
    ("CARTOUCHE", "encre", "CONTINUOUS", 25),
]
CALQUE_FAM = {"temp": "CAPTEURS_THERMIQUES", "count": "CAPTEURS_COMPTAGE",
              "pir": "CAPTEURS_INTRUSION", "infra": "RESEAU", "screen": "AFFICHAGE"}
BLOC_FAM = {"temp": "NOEUD_THERMIQUE", "count": "NOEUD_COMPTAGE", "pir": "NOEUD_INTRUSION",
            "infra": "EQUIPEMENT_RESEAU", "screen": "ECRAN"}

# Types de ligne (motifs en mètres) ; LibreCAD les reconnaît par leur nom
LTYPES = [
    ("CONTINUOUS", "Solid line", []),
    ("DASHED", "Dashed __ __ __", [0.30, -0.20]),
    ("DASHED2", "Dashed (.5x) _ _ _", [0.15, -0.10]),
    ("DASHEDX2", "Dashed (2x) ____ ____", [0.50, -0.30]),
    ("DASHDOT", "Dash dot __ . __ .", [0.50, -0.20, 0.0, -0.20]),
    ("DOT", "Dot . . . .", [0.0, -0.10]),
    ("DOT2", "Dot (.5x) .....", [0.0, -0.20]),
]


# --------------------------------------------------------------------------- écriture DXF
def num(v):
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


# Glyphes absents de la police iso3098 de LibreCAD
REMPLACE = {"→": "->", "≈": "~", "″": '"', "≥": ">="}


def chaine(s):
    """Texte en cp1252 ; les caractères hors page de code passent en \\U+XXXX."""
    for ch, rep in REMPLACE.items():
        s = s.replace(ch, rep)
    out = []
    for ch in s:
        try:
            ch.encode("cp1252")
            out.append(ch)
        except UnicodeEncodeError:
            out.append(f"\\U+{ord(ch):04X}")
    return "".join(out)


class Flux:
    def __init__(self):
        self.l = []

    def t(self, code, val):
        if isinstance(val, float):
            val = num(val)
        self.l += [str(code), str(val)]

    def ent(self, kind, calque, couleur=None, ltype=None):
        self.t(0, kind)
        self.t(8, calque)
        if ltype:
            self.t(6, ltype)
        if couleur:
            aci, rgb = COUL[couleur]
            self.t(62, aci)
            if rgb is not None:
                self.t(420, rgb)

    def pt(self, base, p):
        self.t(base, float(p[0]))
        self.t(base + 10, float(p[1]))
        self.t(base + 20, 0.0)


ENT = Flux()      # section ENTITIES
BLK = Flux()      # section BLOCKS
F = ENT           # flux courant


def ligne(p, q, cal, coul=None, lt=None):
    F.ent("LINE", cal, coul, lt)
    F.pt(10, p)
    F.pt(11, q)


def texte(p, s, h, cal="TEXTES", ancre="start", rot=0.0, coul=None):
    """ancre : start (gauche, ligne de base), middle (centré, ligne de base), center (centré-milieu)."""
    F.ent("TEXT", cal, coul)
    F.pt(10, p)
    F.t(40, float(h))
    F.t(1, chaine(s))
    F.t(41, 0.85)                  # police un peu étroite, comme le plan SVG
    if rot:
        F.t(50, float(rot))
    if ancre != "start":
        F.t(72, 1)
        F.pt(11, p)
        if ancre == "center":
            F.t(73, 2)


def solide(pts, cal, coul=None):
    """Triangle ou quadrilatère plein ; pts dans l'ordre du contour."""
    F.ent("SOLID", cal, coul)
    a, b, c = pts[0], pts[1], pts[2]
    d = pts[3] if len(pts) == 4 else c
    for code, p in zip((10, 11, 12, 13), (a, b, d, c)):   # ordre « nœud papillon » du DXF
        F.pt(code, p)


def remplir(pts, cal, coul):
    """Polygone convexe plein, en éventail de triangles."""
    for i in range(1, len(pts) - 1):
        solide([pts[0], pts[i], pts[i + 1]], cal, coul)


def polyligne(pts, cal, fermee=False, bulges=None, coul=None, lt=None):
    F.ent("POLYLINE", cal, coul, lt)
    F.t(66, 1)
    F.pt(10, (0, 0))
    F.t(70, 1 if fermee else 0)
    for i, p in enumerate(pts):
        F.t(0, "VERTEX")
        F.t(8, cal)
        F.pt(10, p)
        if bulges and bulges[i]:
            F.t(42, float(bulges[i]))
    F.t(0, "SEQEND")
    F.t(8, cal)


def cadre(x0, y0, x1, y1, cal, coul=None, plein=None):
    """Rectangle (coins DXF quelconques), plein et/ou contour."""
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    if plein:
        solide(pts, cal, plein)
    if coul is not False:
        polyligne(pts, cal, True, coul=coul)


def cercle(c, r, cal, coul=None):
    F.ent("CIRCLE", cal, coul)
    F.pt(10, c)
    F.t(40, float(r))


def disque(c, r, cal, coul):
    n = 32
    remplir([(c[0] + r * math.cos(2 * math.pi * k / n), c[1] + r * math.sin(2 * math.pi * k / n))
             for k in range(n)], cal, coul)


def arc(c, r, a0, a1, cal, coul=None, lt=None):
    F.ent("ARC", cal, coul, lt)
    F.pt(10, c)
    F.t(40, float(r))
    F.t(50, float(a0))
    F.t(51, float(a1))


def fleche(pointe, origine, cal, coul=None, lg=0.4, demi=0.18):
    """Pointe de flèche pleine en `pointe`, orientée depuis `origine`."""
    dx, dy = pointe[0] - origine[0], pointe[1] - origine[1]
    d = math.hypot(dx, dy)
    ux, uy = dx / d, dy / d
    bx, by = pointe[0] - ux * lg, pointe[1] - uy * lg
    solide([pointe, (bx - uy * demi, by + ux * demi), (bx + uy * demi, by - ux * demi)], cal, coul)


def inserer(bloc, p, cal):
    F.ent("INSERT", cal)
    F.t(2, bloc)
    F.pt(10, p)


def cote(p1, p2, pdim, vertical, cal="COTES"):
    """Cote linéaire (entité DIMENSION, recalculée par LibreCAD)."""
    F.ent("DIMENSION", cal)
    F.pt(10, pdim)
    mid = ((p1[0] + p2[0]) / 2, pdim[1]) if not vertical else (pdim[0], (p1[1] + p2[1]) / 2)
    F.pt(11, mid)
    F.t(70, 0)
    F.pt(13, p1)
    F.pt(14, p2)
    F.t(50, 90.0 if vertical else 0.0)


# --------------------------------------------------------------------------- blocs (symboles)
def blocs():
    global F
    F = BLK

    def debut(nom):
        F.t(0, "BLOCK"); F.t(8, "0"); F.t(2, nom); F.t(70, 0); F.pt(10, (0, 0)); F.t(3, nom)

    def fin():
        F.t(0, "ENDBLK"); F.t(8, "0")

    # Gabarits identiques au SVG (unités SVG / 20 = mètres)
    debut("NOEUD_THERMIQUE")
    disque((0, 0), 0.55, "0", "temp")
    cercle((0, 0), 0.55, "0", "temp")
    fin()
    debut("NOEUD_COMPTAGE")
    cadre(-0.55, -0.55, 0.55, 0.55, "0", "count", "count")
    fin()
    debut("NOEUD_INTRUSION")
    losange = [(0, 0.65), (0.65, 0), (0, -0.65), (-0.65, 0)]
    solide(losange, "0", "pir")
    polyligne(losange, "0", True, coul="pir")
    fin()
    debut("EQUIPEMENT_RESEAU")
    cadre(-0.9, -0.5, 0.9, 0.5, "0", "infra", "infra")
    fin()
    debut("ECRAN")
    cadre(-1.0, -0.35, 1.0, 0.35, "0", "screen", "screen")
    fin()
    debut("BUZZER")        # haut-parleur 0,4 m tourné vers +X
    cadre(-0.2, -0.15, -0.025, 0.15, "0", "pir", "pir")
    solide([(-0.025, -0.15), (0.2, -0.3), (0.2, 0.3), (-0.025, 0.15)], "0", "pir")
    fin()
    F = ENT


def symbole(fam, p, label, cal=None):
    inserer(BLOC_FAM[fam], p, cal or CALQUE_FAM[fam])
    texte(p, label, H(9.5), cal or CALQUE_FAM[fam], "center", coul="blanc")


def bord(fam, ux, uy):
    """Distance (m) du centre au bord du symbole dans la direction (ux, uy)."""
    return gp.bord(fam, ux, uy) / S


def liaison(a, b, cal, avec_fleche=False):
    ea, eb = gp.EQ[a], gp.EQ[b]
    p, q = m(ea["x"], ea["y"]), m(eb["x"], eb["y"])
    d = math.hypot(q[0] - p[0], q[1] - p[1])
    ux, uy = (q[0] - p[0]) / d, (q[1] - p[1]) / d
    da, db = bord(ea["fam"], ux, -uy), bord(eb["fam"], ux, -uy) + (0.1 if avec_fleche else 0)
    p1 = (p[0] + ux * da, p[1] + uy * da)
    p2 = (q[0] - ux * db, q[1] - uy * db)
    ligne(p1, p2, cal)
    if avec_fleche:
        fleche(p2, p1, cal)


# --------------------------------------------------------------------------- dessin
def mur(a, b, ep, cal):
    """Mur plein d'épaisseur ep (m), axe a→b en coordonnées plan, extrémités carrées."""
    p, q = m(*a), m(*b)
    d = math.hypot(q[0] - p[0], q[1] - p[1])
    ux, uy = (q[0] - p[0]) / d, (q[1] - p[1]) / d
    e = ep / 2
    p = (p[0] - ux * e, p[1] - uy * e)
    q = (q[0] + ux * e, q[1] + uy * e)
    nx, ny = -uy * e, ux * e
    solide([(p[0] + nx, p[1] + ny), (q[0] + nx, q[1] + ny), (q[0] - nx, q[1] - ny), (p[0] - nx, p[1] - ny)], cal)


def porte(charniere, ouvert, ferme):
    h, o, f = m(*charniere), m(*ouvert), m(*ferme)
    ligne(h, o, "PORTES")
    r = math.hypot(o[0] - h[0], o[1] - h[1])
    ao = math.degrees(math.atan2(o[1] - h[1], o[0] - h[0])) % 360
    af = math.degrees(math.atan2(f[1] - h[1], f[0] - h[0])) % 360
    a0, a1 = (ao, af) if (af - ao) % 360 <= 180 else (af, ao)
    arc(h, r, a0, a1, "PORTES", lt="DASHED2")


def decouper(poly, x0, y0, x1, y1):
    """Sutherland-Hodgman : polygone ∩ rectangle."""
    def couper(pts, dedans, inter):
        res = []
        for i, c in enumerate(pts):
            p = pts[i - 1]
            if dedans(c):
                if not dedans(p):
                    res.append(inter(p, c))
                res.append(c)
            elif dedans(p):
                res.append(inter(p, c))
        return res

    def ix(xv):
        return lambda p, c: (xv, p[1] + (c[1] - p[1]) * (xv - p[0]) / (c[0] - p[0]))

    def iy(yv):
        return lambda p, c: (p[0] + (c[0] - p[0]) * (yv - p[1]) / (c[1] - p[1]), yv)

    for dedans, inter in ((lambda p: p[0] >= x0, ix(x0)), (lambda p: p[0] <= x1, ix(x1)),
                          (lambda p: p[1] >= y0, iy(y0)), (lambda p: p[1] <= y1, iy(y1))):
        poly = couper(poly, dedans, inter)
        if not poly:
            break
    return poly


def dessiner():
    zones = {z[0]: z for z in gp.ZONES}

    # ---- Sols des zones
    for code, _, lab, x0, y0, x1, y1, fam in gp.ZONES:
        cadre(*m(x0, y0), *m(x1, y1), "ZONES_FOND", False, f"z-{fam}")

    # ---- Champs PIR : 7 m, 120°, coupés par les murs de leur zone
    for e in gp.EQUIPEMENTS:
        if e["fam"] != "pir":
            continue
        a = math.atan2(e["vise"][1] - e["y"], e["vise"][0] - e["x"])
        secteur = [(e["x"], e["y"])] + [
            (e["x"] + 7 * math.cos(a + math.radians(t)), e["y"] + 7 * math.sin(a + math.radians(t)))
            for t in range(-60, 61, 5)]
        _, _, _, x0, y0, x1, y1, _ = zones[e["zone"]]
        poly = [m(*p) for p in decouper(secteur, x0 + 0.1, y0 + 0.1, x1 - 0.1, y1 - 0.1)]
        remplir(poly, "CHAMP_PIR", "pir-clair")
        polyligne(poly, "CHAMP_PIR", True)

    # ---- Marquages au sol
    ligne(m(10, 8), m(10, 30), "LIMITES_ZONES")
    ligne(m(40, 8), m(40, 30), "LIMITES_ZONES")
    ligne(m(0.6, 26.3), m(49.4, 26.3), "MARQUAGE_SOL")
    ligne(m(0.6, 28.7), m(49.4, 28.7), "MARQUAGE_SOL")
    texte(m(25, 27.75), "ALLÉE PIÉTONNE", H(9.5), "ZONES_NOMS", "middle")

    # ---- Palettes 1,2 × 1,0 m
    for x0, lab in ((1.0, "palettes matières premières"), (41.0, "palettes produits finis")):
        for row in (10.0, 11.6):
            for k in range(4):
                cadre(*m(x0 + k * 2.0, row), *m(x0 + k * 2.0 + 1.2, row + 1.0), "MOBILIER", None, "pal")
        texte(m(x0 + 3.6, 13.4), lab, H(9.5), "MOBILIER", "middle", coul="gris")

    # ---- Convoyeur à rouleaux + machines
    cadre(*m(10.5, gp.CONV_Y0), *m(39.5, gp.CONV_Y1), "CONVOYEUR", None, "conv")
    k = 10.75
    while k < 39.5:
        ligne(m(k, gp.CONV_Y0 + 0.05), m(k, gp.CONV_Y1 - 0.05), "CONVOYEUR")
        k += 0.5
    for rid, proc, x0, x1, seuil, capteur in gp.MACHINES:
        cadre(*m(x0, gp.MACH_Y0), *m(x1, gp.MACH_Y1), "MACHINES", None, "mach")
        cx = (x0 + x1) / 2
        texte(m(cx, 17.75), f"{rid} · {proc}", H(11.5), "MACHINES", "middle")
        texte(m(cx, 18.55), capteur, H(10), "MACHINES", "middle", coul="gris")
        texte(m(cx, 21.9), f"seuil {seuil}", H(11.5), "MACHINES", "middle")
    ligne(m(11, 24.9), m(38.8, 24.9), "TEXTES")
    fleche(m(39, 24.9), m(11, 24.9), "TEXTES")
    texte(m(25, 24.4), "sens du flux produit : réception → M1 → M2 → M3 → expédition", H(9.5),
          "TEXTES", "middle", coul="gris")

    # ---- Murs extérieurs (0,40 m) avec ouvertures, cloisons (0,20 m) avec passages
    for a, b in (((0, 0), (50, 0)), ((50, 0), (50, 17)), ((50, 23), (50, 30)), ((50, 30), (0, 30)),
                 ((0, 30), (0, 23)), ((0, 17), (0, 5)), ((0, 3), (0, 0))):
        mur(a, b, 0.40, "MURS")
    for a, b in (((0, 8), (6.5, 8)), ((7.7, 8), (20, 8)), ((21.2, 8), (37, 8)), ((38.2, 8), (47.5, 8)),
                 ((48.7, 8), (50, 8)), ((8, 0), (8, 5.5)), ((8, 6.7), (8, 8)),
                 ((22, 0), (22, 5.5)), ((22, 6.7), (22, 8)), ((30, 0), (30, 8)), ((40, 0), (40, 8))):
        mur(a, b, 0.20, "CLOISONS")

    # ---- Portes battantes + portes sectionnelles des quais
    porte((0, 3), (1, 3), (0, 4))
    porte((0, 5), (1, 5), (0, 4))
    for xa in (6.5, 20, 37, 47.5):
        porte((xa, 8), (xa, 9.2), (xa + 1.2, 8))
    porte((8, 5.5), (9.2, 5.5), (8, 6.7))
    porte((22, 5.5), (23.2, 5.5), (22, 6.7))
    ligne(m(0, 17), m(0, 23), "QUAIS")
    ligne(m(50, 17), m(50, 23), "QUAIS")
    texte(m(-0.6, 4), "Entrée personnel", H(9.5), "TEXTES", "middle", 90, "gris")
    texte(m(-0.6, 20), "Quai réception · porte sectionnelle 6 m", H(9.5), "TEXTES", "middle", 90, "gris")
    texte(m(50.6, 20), "Quai expédition · porte sectionnelle 6 m", H(9.5), "TEXTES", "middle", 270, "gris")

    # ---- Noms des zones
    for code, _, lab, x0, y0, *_ in gp.ZONES:
        texte(m(x0 + 0.35, y0 + 0.85), lab, H(10.5), "ZONES_NOMS")

    # ---- Liaisons
    for e in gp.EQUIPEMENTS:
        if e["fam"] in ("temp", "count", "pir"):
            liaison(e["id"], "AP", "LIAISON_WIFI", True)
    liaison("AP", "E1", "LIAISON_WIFI", True)
    for a, b in (("AP", "SW"), ("SW", "RTR"), ("SW", "GW"), ("SW", "E2")):
        liaison(a, b, "LIAISON_ETHERNET")
    for e in gp.EQUIPEMENTS:          # barrières IR : émetteur / récepteur de part et d'autre du convoyeur
        if e["fam"] == "count":
            x = e["x"]
            ligne(m(x, e["y"] + 0.55), m(x, gp.CONV_Y0 - 0.2), "CAPTEURS_COMPTAGE")
            cadre(*m(x - 0.2, gp.CONV_Y0 - 0.25), *m(x + 0.2, gp.CONV_Y0 - 0.05), "CAPTEURS_COMPTAGE", None, "count")
            cadre(*m(x - 0.2, gp.CONV_Y1 + 0.05), *m(x + 0.2, gp.CONV_Y1 + 0.25), "CAPTEURS_COMPTAGE", None, "count")
            ligne(m(x, gp.CONV_Y0 - 0.05), m(x, gp.CONV_Y1 + 0.05), "FAISCEAU_IR")
    rtr = gp.EQ["RTR"]
    wan0, wan1 = m(rtr["x"], rtr["y"] - 0.6), u(gp.X(rtr["x"]), 80)
    ligne(wan0, (wan1[0], wan1[1] - 0.1), "LIAISON_WAN")
    fleche(wan1, wan0, "LIAISON_WAN")

    # ---- Libellés des liaisons
    p3, ap = gp.EQ["P3"], gp.EQ["AP"]
    mx, my = (gp.X(p3["x"]) + gp.X(ap["x"])) / 2, (gp.Y(p3["y"]) + gp.Y(ap["y"])) / 2
    ang = math.degrees(math.atan2(gp.Y(p3["y"]) - gp.Y(ap["y"]), gp.X(p3["x"]) - gp.X(ap["x"])))
    texte(u(mx + 40, my - 3), "WiFi 2,4 GHz · MQTT vers AP", H(10), "LIAISON_WIFI", "middle", -ang)
    texte(m(ap["x"] - 0.35, 10.3), "Ethernet Cat6 (PoE)", H(10), "LIAISON_ETHERNET", "middle", 90)
    texte(u(gp.X(rtr["x"]) + 12, 100), "WAN 4G / fibre", H(10), "LIAISON_WAN")

    # ---- Symboles des équipements (blocs) + buzzers des PIR
    for e in gp.EQUIPEMENTS:
        symbole(e["fam"], m(e["x"], e["y"]), e["id"])
    for pid, dx in (("P1", 1.05), ("P2", 1.05), ("P3", -1.05)):
        e = gp.EQ[pid]
        F.ent("INSERT", "CAPTEURS_INTRUSION")
        F.t(2, "BUZZER")
        F.pt(10, m(e["x"] + dx, e["y"]))
        if dx < 0:
            F.t(50, 180.0)

    def lab(eid, dx, dy, s, ancre="start", petit=False):
        e = gp.EQ[eid]
        texte(u(gp.X(e["x"]) + dx, gp.Y(e["y"]) + dy), s, H(9.5 if petit else 11), "TEXTES", ancre,
              coul="gris" if petit else None)
    lab("RTR", 22, 4, "Routeur 4G / fibre")
    lab("SW", 22, 4, "Switch")
    lab("GW", 0, 24, "Passerelle", "middle")
    lab("GW", 0, 36, "Raspberry Pi 4", "middle", True)
    lab("UPS", 22, 4, "Onduleur")
    lab("AP", 24, -4, "Point d'accès WiFi")
    lab("AP", 24, 8, "plafond, h ≈ 6 m", petit=True)
    lab("E1", 0, 21, "Écran 15″ kiosque", "middle")
    lab("E2", 0, -13, "Poste de supervision", "middle")

    # ---- Monde extérieur : Internet → services en ligne → smartphone
    rx = gp.X(rtr["x"])
    (xa, yh), (xb, yb) = u(rx - 75, 22), u(rx + 75, 78)
    r = (yh - yb) / 2
    polyligne([(xa + r, yb), (xb - r, yb), (xb - r, yh), (xa + r, yh)], "EXTERIEUR", True,
              [0, 1, 0, 1], coul="wan")
    texte(u(rx, 46), "Internet", H(11), "EXTERIEUR", "middle")
    texte(u(rx, 62), "4G · fibre optique", H(9.5), "EXTERIEUR", "middle", coul="gris")
    cadre(*u(690, 22), *u(910, 78), "EXTERIEUR")
    texte(u(800, 46), "Services en ligne", H(11), "EXTERIEUR", "middle")
    texte(u(800, 62), "SMTP Gmail · API SMS Orange / MTN", H(9.5), "EXTERIEUR", "middle", coul="gris")
    cadre(*u(985, 22), *u(1125, 78), "EXTERIEUR")
    texte(u(1055, 46), "Smartphone", H(11), "EXTERIEUR", "middle")
    texte(u(1055, 62), "du responsable", H(9.5), "EXTERIEUR", "middle", coul="gris")
    for x0, x1, s in ((rx + 75, 690, "alerte"), (910, 985, "email · SMS")):
        ligne(u(x0, 50), u(x1 - 8, 50), "EXTERIEUR")
        fleche(u(x1, 50), u(x0, 50), "EXTERIEUR")
        texte(u((x0 + x1) / 2, 44), s, H(9.5), "EXTERIEUR", "middle", coul="gris")

    # ---- Cotes (entités DIMENSION, modifiables dans LibreCAD)
    def chaine_h(ydim, xs, ymur):
        for a, b in zip(xs, xs[1:]):
            cote((a, ymur), (b, ymur), (b, ydim), False)

    def chaine_v(xdim, ys, xmur):
        for a, b in zip(ys, ys[1:]):
            cote((xmur, ZMAX - a), (xmur, ZMAX - b), (xdim, ZMAX - b), True)
    chaine_h(u(0, 128)[1], [0, 8, 22, 30, 40, 50], ZMAX)
    chaine_h(u(0, 772)[1], [0, 10, 40, 50], 0)
    chaine_h(u(0, 800)[1], [0, 50], 0)
    chaine_v(u(30, 0)[0], [0, 30], 0)
    chaine_v(u(1100, 0)[0], [0, 8, 30], 50)

    # ---- Échelle graphique + nord
    y0, y1 = u(0, 826)[1], u(0, 832)[1]
    for i in range(4):
        cadre(i * 5, y0, i * 5 + 5, y1, "LEGENDE", None, "encre" if i % 2 == 0 else None)
    for i, v in enumerate(("0", "5", "10", "15", "20 m")):
        texte((i * 5, u(0, 848)[1]), v, H(10), "LEGENDE", "middle")
    texte(u(gp.OX + 20 * S + 20, 833), "Échelle graphique · 1 unité = 1 m", H(9.5), "LEGENDE", coul="gris")
    nx, ny = 760, 838
    pointe, droite, creux, gauche = u(nx, ny - 24), u(nx + 8, ny), u(nx, ny - 6), u(nx - 8, ny)
    solide([pointe, droite, creux], "LEGENDE")
    solide([pointe, creux, gauche], "LEGENDE")
    texte(u(nx, ny + 14), "N", H(11), "LEGENDE", "middle")

    # ---- En-tête
    texte(u(gp.OX, 44), "PLAN D'IMPLANTATION · RDC", H(21), "CARTOUCHE")
    texte(u(gp.OX, 64), "Usine · 50 × 30 m (1 500 m²) · système IoT de surveillance", H(11.5),
          "CARTOUCHE", coul="gris")

    legende()
    cartouche()


def legende():
    lx, ly = 1140, 160
    texte(u(lx, ly), "ÉQUIPEMENTS", H(10), "LEGENDE", coul="gris")
    rows = [("temp", "T", "Nœud thermique · ESP32 + sonde (×3)"),
            ("count", "C", "Nœud de comptage · barrière IR (×3)"),
            ("pir", "P", "Nœud intrusion · PIR + buzzer (×3)"),
            ("infra", "GW", "Réseau, passerelle, alimentation"),
            ("screen", "E", "Affichage du tableau de bord")]
    for i, (fam, sid, s) in enumerate(rows):
        yy = ly + 26 + i * 25
        symbole(fam, u(lx + 20, yy), sid, "LEGENDE")
        texte(u(lx + 46, yy + 4), s, H(11), "LEGENDE")
    ly2 = ly + 26 + 5 * 25 + 8
    texte(u(lx, ly2), "LIAISONS", H(10), "LEGENDE", coul="gris")
    lrows = [("LIAISON_WIFI", None, "Radio WiFi 2,4 GHz · MQTT"),
             ("LIAISON_ETHERNET", None, "Câble Ethernet Cat6"),
             ("LIAISON_WAN", None, "Sortie Internet (4G / fibre)"),
             ("FAISCEAU_IR", None, "Faisceau IR de comptage"),
             ("PORTES", "DASHED2", "Débattement de porte")]
    for i, (cal, lt, s) in enumerate(lrows):
        yy = ly2 + 22 + i * 22
        ligne(u(lx + 2, yy), u(lx + 38, yy), cal, lt=lt)
        texte(u(lx + 46, yy + 4), s, H(11), "LEGENDE")
    yy = ly2 + 22 + 5 * 22
    tri = [u(lx + 4, yy + 7), u(lx + 36, yy + 7), u(lx + 20, yy - 7)]
    solide(tri, "CHAMP_PIR", "pir-clair")
    polyligne(tri, "CHAMP_PIR", True)
    texte(u(lx + 46, yy + 4), "Champ PIR · 7 m, 120°", H(11), "LEGENDE")
    ly3 = yy + 30
    texte(u(lx, ly3), "ZONES", H(10), "LEGENDE", coul="gris")
    zrows = [("z-office", "Bureaux"), ("z-tech", "Technique"), ("z-prod", "Production"),
             ("z-store", "Stockage"), ("z-neutral", "Annexes")]
    for i, (coul, s) in enumerate(zrows):
        cx, cy = lx + (i % 3) * 95, ly3 + 14 + (i // 3) * 22
        cadre(*u(cx, cy - 1), *u(cx + 22, cy + 13), "LEGENDE", "gris", coul)
        texte(u(cx + 28, cy + 10), s, H(11), "LEGENDE")


def cartouche():
    cx0, cy0, cw = 1140, 640, 285
    C = "CARTOUCHE"
    cadre(*u(cx0, cy0), *u(cx0 + cw, cy0 + 210), C)
    texte(u(cx0 + 10, cy0 + 22), "IFRI · RÉSEAUX DE CAPTEURS & IOT", H(14), C)

    def regle(dy):
        ligne(u(cx0, cy0 + dy), u(cx0 + cw, cy0 + dy), C)

    def champ(x, dy, k, v):
        texte(u(x + 10, cy0 + dy), k, H(8.5), C, coul="gris")
        texte(u(x + 10, cy0 + dy + (15 if dy < 120 else 20)), v, H(11.5), C)
    regle(34)
    champ(cx0, 48, "PROJET", "Surveillance d'une ligne de production")
    regle(74)
    champ(cx0, 88, "PLANCHE", "Implantation physique des équipements")
    regle(114)
    for top, cells in ((114, [("ÉCHELLE", "graphique"), ("DATE", "19/10/2026"), ("INDICE", "A")]),
                       (162, [("DESSINÉ PAR", "Groupe 7"), ("NIVEAU", "RDC"), ("PLANCHE", "01 / 01")])):
        for i, (k_, v) in enumerate(cells):
            x_ = cx0 + i * 95
            if i:
                ligne(u(x_, cy0 + top), u(x_, cy0 + top + 48), C)
            champ(x_, top + 16, k_, v)
        if top == 114:
            regle(162)


# --------------------------------------------------------------------------- assemblage
def entete():
    h = Flux()
    h.t(0, "SECTION"); h.t(2, "HEADER")
    xmin, ymax = u(0, 0)
    xmax, ymin = u(gp.VB_W, gp.VB_H)
    variables = [
        ("$ACADVER", 1, "AC1009"), ("$DWGCODEPAGE", 3, "ANSI_1252"),
        ("$INSUNITS", 70, 6), ("$LUNITS", 70, 2), ("$LUPREC", 70, 2), ("$LTSCALE", 40, 1.0),
        ("$DIMSCALE", 40, 1.0), ("$DIMLFAC", 40, 1.0), ("$DIMRND", 40, 0.0), ("$DIMTXT", 40, H(10)), ("$DIMASZ", 40, 0.2), ("$DIMTSZ", 40, 0.2),
        ("$DIMEXO", 40, 0.3), ("$DIMEXE", 40, 0.3), ("$DIMGAP", 40, 0.1), ("$DIMDEC", 70, 2),
        ("$DIMZIN", 70, 0), ("$DIMDSEP", 70, 44), ("$DIMLUNIT", 70, 2), ("$DIMTAD", 70, 1),
    ]
    for nom, code, val in variables:
        h.t(9, nom)
        h.t(code, float(val) if isinstance(val, float) else val)
    h.t(9, "$EXTMIN"); h.pt(10, (xmin, ymin))
    h.t(9, "$EXTMAX"); h.pt(10, (xmax, ymax))
    h.t(9, "$LIMMIN"); h.t(10, num(xmin)); h.t(20, num(ymin))
    h.t(9, "$LIMMAX"); h.t(10, num(xmax)); h.t(20, num(ymax))
    h.t(0, "ENDSEC")
    return h.l


def tables():
    t = Flux()
    t.t(0, "SECTION"); t.t(2, "TABLES")
    t.t(0, "TABLE"); t.t(2, "LTYPE"); t.t(70, len(LTYPES))
    for nom, desc, motif in LTYPES:
        t.t(0, "LTYPE"); t.t(2, nom); t.t(70, 0); t.t(3, desc); t.t(72, 65)
        t.t(73, len(motif)); t.t(40, float(sum(abs(v) for v in motif)))
        for v in motif:
            t.t(49, float(v))
    t.t(0, "ENDTAB")
    t.t(0, "TABLE"); t.t(2, "LAYER"); t.t(70, len(CALQUES))
    for nom, coul, lt, lw in CALQUES:
        aci, rgb = COUL[coul]
        t.t(0, "LAYER"); t.t(2, nom); t.t(70, 0); t.t(62, aci)
        if rgb is not None:
            t.t(420, rgb)
        t.t(6, lt); t.t(370, lw)
    t.t(0, "ENDTAB")
    t.t(0, "TABLE"); t.t(2, "STYLE"); t.t(70, 1)
    t.t(0, "STYLE"); t.t(2, "STANDARD"); t.t(70, 0); t.t(40, 0.0); t.t(41, 1.0); t.t(50, 0.0)
    t.t(71, 0); t.t(42, 0.4); t.t(3, "iso3098"); t.t(4, "")
    t.t(0, "ENDTAB")
    t.t(0, "ENDSEC")
    return t.l


def main():
    blocs()
    dessiner()
    lignes = entete() + tables()
    lignes += ["0", "SECTION", "2", "BLOCKS"] + BLK.l + ["0", "ENDSEC"]
    lignes += ["0", "SECTION", "2", "ENTITIES"] + ENT.l + ["0", "ENDSEC", "0", "EOF"]
    sortie = gp.ICI / "plan_implantation.dxf"
    sortie.write_text("\n".join(lignes) + "\n", encoding="cp1252", newline="\r\n")
    print(f"OK : {sortie.name} ({len(ENT.l) // 2} codes, {len(CALQUES)} calques)")


if __name__ == "__main__":
    main()
