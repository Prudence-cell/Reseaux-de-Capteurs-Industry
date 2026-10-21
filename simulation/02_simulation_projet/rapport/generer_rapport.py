# -*- coding: utf-8 -*-
"""
Génère le rapport de simulation (HTML + PDF) à partir des journaux de test.

    python rapport/generer_rapport.py

Entrées  : resultats/*.log (copiés par tester.sh), le code nesC (extraits), le plan
           (architecture/generer_plan.py) pour la carte.
Sorties  : rapport/figures/*.png, rapport/rapport_simulation.html, rapport/rapport_simulation.pdf
Toutes les valeurs chiffrées du rapport viennent des journaux : relancer tester.sh puis ce
script met le rapport à jour.
"""
import html
import importlib.util
import pathlib
import re
import subprocess
import sys
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                      # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle   # noqa: E402

ICI = pathlib.Path(__file__).resolve().parent
PROJET = ICI.parent
RES = PROJET / "resultats"
FIG = ICI / "figures"
ARCHI = PROJET.parent.parent / "architecture"
FIG.mkdir(exist_ok=True)

# Le plan d'implantation (zones, machines, positions) : on importe le script du plan
spec = importlib.util.spec_from_file_location("plan", ARCHI / "generer_plan.py")
plan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plan)
NOEUDS = {e["cooja"]: e for e in plan.EQUIPEMENTS if e["cooja"]}

# Couleurs : familles = jetons du plan d'implantation ; séries = palette catégorielle validée
FAM = {"infra": "#0E746D", "temp": "#C63F29", "count": "#1F66AE", "pir": "#7B3FAF"}
SERIE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
ENCRE, GRIS, TRAIT = "#17293B", "#5A6B7B", "#CDD6DE"
plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 9, "axes.edgecolor": TRAIT,
    "axes.labelcolor": ENCRE, "xtick.color": GRIS, "ytick.color": GRIS, "axes.grid": True,
    "grid.color": "#E6EBEF", "grid.linewidth": 0.6, "axes.spines.top": False,
    "axes.spines.right": False, "axes.titleweight": "bold", "axes.titlesize": 10,
    "axes.titlecolor": ENCRE, "legend.frameon": False, "figure.dpi": 100,
})


# ============================================================================ lecture des journaux
class Journal:
    """Un journal de test : lignes L (t_ms, nœud, texte), MESURE, VERDICT, ARBRE, CMD."""

    def __init__(self, nom):
        self.nom = nom
        self.lignes, self.mesures, self.verdicts, self.arbre, self.cmd = [], {}, [], {}, []
        self.fin = None
        chemin = RES / f"{nom}.log"
        self.existe = chemin.exists()
        if not self.existe:
            return
        for brut in chemin.read_text(encoding="utf-8", errors="replace").splitlines():
            if brut.startswith("L "):
                p = brut.split(" ", 3)
                if len(p) == 4:
                    self.lignes.append((float(p[1]), int(p[2]), p[3]))
            elif brut.startswith("MESURE "):
                m = re.match(r"MESURE (\S+)=(\S+)\s*(.*)", brut)
                if m:
                    try:
                        self.mesures[m.group(1)] = (float(m.group(2)), m.group(3))
                    except ValueError:
                        self.mesures[m.group(1)] = (m.group(2), m.group(3))
            elif brut.startswith("VERDICT "):
                m = re.match(r"VERDICT (\S+) (OK|ECHEC) (.*)", brut)
                if m:
                    self.verdicts.append((m.group(1), m.group(2) == "OK", m.group(3)))
            elif brut.startswith("ARBRE "):
                m = re.match(r"ARBRE (\d+) -> (\d+) sauts=(\d+)", brut)
                if m:
                    self.arbre[int(m.group(1))] = (int(m.group(2)), int(m.group(3)))
            elif brut.startswith("CMD "):
                m = re.match(r"CMD (\S+) noeud (\d+) <- (.*)", brut)
                if m:
                    self.cmd.append((float(m.group(1)), int(m.group(2)), m.group(3)))
            elif brut.startswith("FIN "):
                self.fin = brut

    def m(self, cle, defaut=None):
        return self.mesures.get(cle, (defaut, ""))[0]

    def latences(self):
        """Latence de chaque rapport (PUB sur le capteur -> RX à la passerelle), en ms."""
        pubs, res = {}, []
        for t, n, msg in self.lignes:
            if msg.startswith("PUB "):
                pubs[(n, re.search(r"seq=(\d+)", msg).group(1))] = t
            elif n == 1 and msg.startswith("RX "):
                src = int(re.search(r"src=(\d+)", msg).group(1))
                seq = re.search(r"seq=(\d+)", msg).group(1)
                diff = re.search(r"diff=(\d)", msg).group(1) == "1"
                sauts = int(re.search(r"sauts=(\d+)", msg).group(1))
                t0 = pubs.pop((src, seq), None)
                if t0 is not None:
                    res.append(dict(src=src, ms=t - t0, sauts=sauts, diff=diff, t=t))
        return res


J = {n: Journal(n) for n in ["T1_periode", "T2_surchauffe", "T4_comptage", "T5_intrusion",
                             "T6_reseau", "T6b_pertes", "T7_coupure", "T9_panne", "ENF6_auth",
                             "E_energie", "E_energie_lpl", "E_energie_lpl1024", "E_energie_lpl2048"]}


def fmt(v, n=1, unite=""):
    if v is None or isinstance(v, str):
        return "—" if v is None else v
    s = f"{v:.{n}f}".replace(".", ",")
    return s + (f" {unite}" if unite else "")


def sauver(fig, nom):
    fig.savefig(FIG / f"{nom}.png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return f"figures/{nom}.png"


# ============================================================================ figures
def dessiner_plan(ax, arbre, retire=None, titre=""):
    """Le bâtiment (zones du plan), les nœuds et l'arbre CTP (flèche enfant -> parent)."""
    for code, nom, lab, x0, y0, x1, y1, fam in plan.ZONES:
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor="#F4F6F8", edgecolor="#B8C2CC", lw=0.8))
        ax.text(x0 + 0.5, y0 + 1.2, code, fontsize=7, color=GRIS)
    for rep, proc, x0, x1, *_ in plan.MACHINES:
        ax.add_patch(Rectangle((x0, plan.MACH_Y0), x1 - x0, plan.MACH_Y1 - plan.MACH_Y0,
                               facecolor="#DDE3E9", edgecolor="#9AA6B2", lw=0.6))
        ax.text((x0 + x1) / 2, plan.MACH_Y1 - 1.5, rep, ha="center", fontsize=7, color=GRIS)
    gw = NOEUDS[1]
    ax.add_patch(Circle((gw["x"], gw["y"]), plan.PORTEE_COOJA, fill=False, ls="--", lw=0.9, ec=FAM["infra"]))
    ax.text(gw["x"] + 14.5, gw["y"] + 15.5, f"portée {plan.PORTEE_COOJA} m", color=FAM["infra"], fontsize=7)
    for enfant, (parent, _) in arbre.items():
        if enfant not in NOEUDS or parent not in NOEUDS:
            continue
        a, b = NOEUDS[enfant], NOEUDS[parent]
        d = ((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2) ** 0.5
        ax.add_patch(FancyArrowPatch((a["x"], a["y"]), (b["x"], b["y"]), arrowstyle="-|>", mutation_scale=9,
                                     # courbées (davantage si courtes) : aucune flèche ne passe sous un autre nœud
                                     connectionstyle=f"arc3,rad={0.5 if d < 12 else 0.18}",
                                     lw=1.3, color=ENCRE, shrinkA=7, shrinkB=7, zorder=3))
    for n, e in NOEUDS.items():
        mort = (n == retire)
        ax.scatter(e["x"], e["y"], s=230, color="white" if mort else FAM[e["fam"]],
                   edgecolor=FAM[e["fam"]], lw=1.5, zorder=4)
        ax.text(e["x"], e["y"], str(n), ha="center", va="center", fontsize=7.5, fontweight="bold",
                color=FAM[e["fam"]] if mort else "white", zorder=5)
        ax.text(e["x"] + 1.3, e["y"] - 1.3, e["id"] + (" (retiré)" if mort else ""), ha="left", va="bottom",
                fontsize=7, color=ENCRE, zorder=6,
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.85))
    ax.set_xlim(-1, 51); ax.set_ylim(31, -1)
    ax.set_aspect("equal"); ax.grid(False)
    ax.set_xlabel("x (m)"); ax.set_ylabel("y (m)")
    ax.set_title(titre, loc="left")


def fig_topologie():
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.9))
    dessiner_plan(axes[0], J["T6_reseau"].arbre, titre="Arbre CTP en fonctionnement normal (T6)")
    dessiner_plan(axes[1], J["T9_panne"].arbre, retire=2, titre="Après le retrait du relais T1 (T9)")
    for fam, lab in [("infra", "passerelle"), ("temp", "thermique"), ("count", "comptage"), ("pir", "intrusion")]:
        axes[1].scatter([], [], s=60, color=FAM[fam], label=lab)
    axes[1].legend(loc="lower right", fontsize=7, ncol=4, bbox_to_anchor=(1, -0.32))
    return sauver(fig, "topologie")


def fig_latence():
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.2), sharey=True)
    for ax, nom, titre in [(axes[0], "T6_reseau", "Liens parfaits (T6)"),
                           (axes[1], "T6b_pertes", "Liens dégradés : 80 % de réussite à 20 m (T6b)")]:
        lat = [l for l in J[nom].latences() if not l["diff"]]
        groupes = sorted({l["sauts"] for l in lat})
        donnees = [[l["ms"] for l in lat if l["sauts"] == s] for s in groupes]
        if donnees:
            b = ax.boxplot(donnees, tick_labels=[f"{s} saut{'s' if s > 1 else ''}\n(n={len(d)})" for s, d in zip(groupes, donnees)],
                           widths=0.45, patch_artist=True, showfliers=True,
                           flierprops=dict(marker="o", ms=3, mfc=SERIE[0], mec="white", alpha=.7),
                           medianprops=dict(color=ENCRE, lw=1.4))
            for p in b["boxes"]:
                p.set(facecolor="#D6E6F8", edgecolor=SERIE[0])
        ax.set_title(titre, loc="left")
    axes[0].set_ylabel("latence capteur → passerelle (ms)")
    return sauver(fig, "latence")


def fig_energie():
    cfg = [("E_energie", "radio\ntoujours allumée"), ("E_energie_lpl", "LPL\n512 ms"),
           ("E_energie_lpl1024", "LPL\n1024 ms"), ("E_energie_lpl2048", "LPL\n2048 ms")]
    cfg = [(n, l) for n, l in cfg if J[n].existe]
    pref = {"E_energie": "E", "E_energie_lpl": "E_lpl", "E_energie_lpl1024": "E_lpl1024", "E_energie_lpl2048": "E_lpl2048"}
    duty, auto, lat = [], [], []
    for n, _ in cfg:
        d = J[n].m(pref[n] + "_radio_on_capteurs_moy", 0)
        duty.append(d)
        auto.append(2000.0 / (d / 100 * 19.0 + 0.1) / 24)
        lat.append(J[n].m(pref[n] + "_latence_moy", 0))
    labels = [l for _, l in cfg]
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.1))
    for ax, val, titre, fmt_v in [(axes[0], duty, "Radio allumée (moyenne des capteurs, %)", "{:.1f} %"),
                                  (axes[1], auto, "Autonomie estimée, batterie 2000 mAh (jours)", "{:.0f} j"),
                                  (axes[2], lat, "Latence moyenne capteur → passerelle (ms)", "{:.0f} ms")]:
        barres = ax.bar(labels, val, color=SERIE[0], width=0.55, edgecolor="white", linewidth=2)
        for b, v in zip(barres, val):
            ax.text(b.get_x() + b.get_width() / 2, b.get_height(), fmt_v.format(v).replace(".", ","),
                    ha="center", va="bottom", fontsize=8, color=ENCRE)
        ax.set_title(titre, loc="left", fontsize=9)
        ax.tick_params(axis="x", labelsize=7.5)
        ax.margins(y=0.15)
        ax.grid(axis="x", visible=False)
    axes[1].axhline(182, color=FAM["temp"], ls="--", lw=1)
    axes[1].text(len(labels) - 0.5, 186, "ENF5 : 6 mois", color=FAM["temp"], fontsize=7.5, ha="right", va="bottom")
    return sauver(fig, "energie")


def fig_t2():
    j = J["T2_surchauffe"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.1))
    for ax, noeuds in [(axes[0], [2, 3]), (axes[1], [4])]:
        for k, n in enumerate(noeuds):
            pts = [(t / 1000, int(re.search(r"val=(-?\d+)", m).group(1)) / 10) for t, nn, m in j.lignes
                   if nn == n and m.startswith("PUB ") and "type=1" in m]
            if pts:
                coul = SERIE[k] if len(noeuds) > 1 else SERIE[2]
                ax.plot(*zip(*pts), marker="o", ms=3.5, lw=2, color=coul,
                        label=f"{NOEUDS[n]['id']} – {plan.MACHINES[plan_index(n)][0]} {plan.MACHINES[plan_index(n)][1]}")
                seuil = int(plan.MACHINES[plan_index(n)][4].split()[0])
                ax.axhline(seuil, color=coul, ls="--", lw=1)
                ax.text(1.0, seuil, f"seuil {seuil} °C ", color=coul, fontsize=7, va="bottom", ha="right",
                        transform=ax.get_yaxis_transform())
        for t, n, c in j.cmd:
            if n in noeuds:
                ax.axvline(t / 1000, color=GRIS, lw=0.8, ls=":")
                ax.text(t / 1000 + 2, ax.get_ylim()[0] + 2, "sonde forcée" if c == "H" else "retour normal",
                        rotation=90, fontsize=7, color=GRIS, va="bottom")
        for t, n, m in j.lignes:
            if n == 1 and m.startswith("ALERTE SURCHAUFFE") and any(f"src={x} " in m for x in noeuds):
                ax.plot(t / 1000, float(re.search(r"temp=([\d.]+)", m).group(1)), marker="v", ms=9,
                        color=FAM["temp"], zorder=5)
        ax.set_xlabel("temps de simulation (s)"); ax.set_ylabel("température rapportée (°C)")
        ax.legend(loc="lower right", fontsize=7.5)
    axes[0].set_title("Découpe et presse : la presse passe à 95 °C à t = 120 s", loc="left")
    axes[1].set_title("Four : 185 °C sans alerte, alerte à 225 °C", loc="left")
    return sauver(fig, "t2_temperatures")


def plan_index(n):
    return int(NOEUDS[n]["id"][1]) - 1


def fig_t7():
    j = J["T7_coupure"]
    dep = [l for l in open(RES / "T7_coupure.log", encoding="utf-8") if l.startswith("DEPLACEMENT")] if j.existe else []
    tcoup = [float(l.split()[1]) / 1000 for l in dep]
    fig, axes = plt.subplots(2, 1, figsize=(10, 4.6), sharex=True)
    pts = [(t / 1000 / 60, int(re.search(r"attente=(\d+)", m).group(1))) for t, nn, m in j.lignes
           if nn == 8 and m.startswith("PUB ")]
    if pts:   # les 9 capteurs ont le même profil (1 rapport / 30 s) : on en montre un
        axes[0].step(*zip(*pts), where="post", lw=2, color=SERIE[0], label="P1 (nœud 8) — profil identique pour les 9 capteurs")
    axes[0].set_ylabel("rapports dans\nle tampon")
    axes[0].legend(loc="upper left", fontsize=7.5, ncol=3)
    cumul, c = [], 0
    for t, n, m in j.lignes:
        if n == 1 and m.startswith("RX "):
            c += 1
            cumul.append((t / 1000 / 60, c))
    if cumul:
        axes[1].plot(*zip(*cumul), lw=2, color=SERIE[0])
    axes[1].set_ylabel("rapports reçus\n(cumul passerelle)")
    axes[1].set_xlabel("temps de simulation (min)")
    for ax in axes:
        if len(tcoup) >= 2:
            ax.axvspan(tcoup[0] / 60, tcoup[1] / 60, color="#FBEDE6", zorder=0)
    if len(tcoup) >= 2:
        axes[0].text((tcoup[0] + tcoup[1]) / 120, axes[0].get_ylim()[1] * 0.9, "passerelle hors de portée (1 h)",
                     ha="center", fontsize=8, color=FAM["temp"])
    axes[0].set_title("Coupure d'1 h : les capteurs stockent, puis tout est renvoyé au retour (T7)", loc="left")
    return sauver(fig, "t7_coupure")


# ============================================================================ morceaux HTML
def esc(t):
    return html.escape(str(t))


def extrait(fichier, debut, nb):
    """Extrait nb lignes du code source à partir de la première ligne qui contient « debut »."""
    lignes = (PROJET / fichier).read_text(encoding="utf-8").splitlines()
    for i, l in enumerate(lignes):
        if debut in l:
            bloc = "\n".join(lignes[i:i + nb])
            return f'<pre><code>{esc(bloc)}</code></pre><p class="src">{esc(fichier)}, ligne {i + 1}</p>'
    return f"<p>(extrait introuvable : {esc(fichier)})</p>"


def tableau(entetes, lignes, classe=""):
    h = "".join(f"<th>{esc(e)}</th>" for e in entetes)
    corps = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in l) + "</tr>" for l in lignes)
    return f'<table class="{classe}"><thead><tr>{h}</tr></thead><tbody>{corps}</tbody></table>'


def badge(ok):
    return '<span class="ok">✔ conforme</span>' if ok else '<span class="ko">✘ non conforme</span>'


def verdict_de(nom_journal, nom_verdict):
    for n, ok, d in J[nom_journal].verdicts:
        if n == nom_verdict:
            return ok, d
    return None, "test non exécuté"


# ============================================================================ tableau des exigences
BILAN = (0, 0, 0)

def exigences():
    t1, t2, t4, t5, t6, t6b, t7, t9, e6 = (J[n] for n in ["T1_periode", "T2_surchauffe", "T4_comptage",
                                                         "T5_intrusion", "T6_reseau", "T6b_pertes",
                                                         "T7_coupure", "T9_panne", "ENF6_auth"])
    lignes = []

    def ajoute(exig, test, mesure, ok):
        lignes.append([exig, test, mesure, "—" if ok is None else badge(ok)])

    ok, _ = verdict_de("T1_periode", "T1")
    ajoute("EF1 — une mesure toutes les 30 s ± 2 s", "T1 (10 min, 9 capteurs)",
           f"écart entre rapports : {fmt(t1.m('T1_ecart_min'), 2)} à {fmt(t1.m('T1_ecart_max'), 2)} s "
           f"({fmt(t1.m('T1_n'), 0)} intervalles)", ok)
    ok, d = verdict_de("T1_periode", "T1_fidelite")
    ajoute("EF1 — valeur transmise sans altération", "T1", esc(d.split(" (")[0]), ok)
    ok, _ = verdict_de("T2_surchauffe", "T2")
    ajoute("EF2 + ENF1 — 95 °C → alerte < 10 s (cible 5 s)", "T2 (presse M2, seuil 90 °C)",
           f"alerte {fmt(t2.m('T2_latence_injection_alerte_M2', 0) / 1000, 2)} s après la mise à 95 °C", ok)
    ok, _ = verdict_de("T2_surchauffe", "T2_seuil_par_machine")
    ajoute("EF2 — seuil propre à chaque machine", "T2 (four M3, seuil 220 °C)",
           f"185 °C sans alerte ; 225 °C → alerte en {fmt(t2.m('T2_latence_injection_alerte_M3', 0) / 1000, 2)} s", ok)
    ok, _ = verdict_de("T4_comptage", "T4")
    ajoute("EF5 — 100 pièces → compteur = 100", "T4 (poste C1)",
           f"compteur local {fmt(t4.m('T4_compteur_local_C1'), 0)}, reçu par la passerelle "
           f"{fmt(t4.m('T4_compteur_passerelle_C1'), 0)}", ok)
    ok, _ = verdict_de("T4_comptage", "T4_redemarrage")
    ajoute("EF5 — le compteur survit à un redémarrage", "T4 (poste C2, chien de garde)",
           f"{fmt(t4.m('T4_C2_avant_redemarrage'), 0)} pièces avant, {fmt(t4.m('T4_C2_restaure'), 0)} restaurées", ok)
    ok, _ = verdict_de("T5_intrusion", "T5")
    lat5 = [t5.m(f"T5_latence_ZONE_0{i}", 0) for i in (1, 2, 3)]
    ajoute("EF6 — présence hors 08h–18h → alerte < 5 s", "T5 (P1, P2, P3 à 19h00)",
           f"alerte en {fmt(max(lat5) / 1000, 2)} s au pire (3 zones), buzzer local activé", ok)
    ok, d = verdict_de("T5_intrusion", "T5_pas_alerte_de_jour")
    ajoute("B4 — pas d'alerte pendant les heures ouvrées", "T5 (17h30 et 08h30)", esc(d), ok)
    ok, _ = verdict_de("T6_reseau", "T6")
    ajoute("ENF1 / T6 — latence totale < 10 s", "T6 (20 min, 10 nœuds)",
           f"capteur → passerelle : moyenne {fmt(t6.m('T6_latence_moy'), 1)} ms, max {fmt(t6.m('T6_latence_max'), 0)} ms", ok)
    ok, _ = verdict_de("T6_reseau", "T6_budget_radio")
    ajoute("ENF1 — budget nœud → passerelle < 1 s", "T6", f"95 % des rapports en moins de {fmt(t6.m('T6_latence_p95'), 0)} ms", ok)
    ok, _ = verdict_de("T6_reseau", "T6_pdr")
    ajoute("B3 — données centralisées (taux de livraison)", "T6 / T6b",
           f"PDR {fmt(t6.m('T6_pdr_global'), 2)} % (liens parfaits), {fmt(t6b.m('T6b_pdr_global'), 2)} % (liens dégradés)",
           ok and verdict_de("T6b_pertes", "T6b_pdr")[0])
    ok, _ = verdict_de("T7_coupure", "T7")
    ajoute("ENF3 / T7 — coupure d'1 h : données gardées puis renvoyées", "T7 (passerelle hors de portée 1 h)",
           f"{fmt(t7.m('T7_recuperes'), 0)} / {fmt(t7.m('T7_publies_pendant_coupure'), 0)} rapports récupérés, "
           f"tampons vidés en {fmt(t7.m('T7_temps_vidage'), 0)} s", ok)
    ok, _ = verdict_de("T7_coupure", "T7_horodatage")
    ajoute("ENF3 — horodatage de la mesure conservé", "T7", f"écart max {fmt(t7.m('T7_ecart_horodatage_max'), 1)} s (critère retenu : ± 5 s)", ok)
    ok, _ = verdict_de("T9_panne", "T9")
    ajoute("ENF8 / T9 — un nœud retiré, les autres continuent", "T9 (retrait du relais T1)",
           f"8/8 capteurs continuent, PDR après la panne {fmt(t9.m('T9_pdr_autres'), 1)} %", ok)
    ok, _ = verdict_de("T9_panne", "T9_reroutage_P1")
    ajoute("ENF8 — reconvergence du routage", "T9 (P1, qui passait par T1)",
           f"nouveau parent en {fmt(t9.m('T9_reconvergence'), 1)} s, rapports rétablis en {fmt(t9.m('T9_retablissement_P1'), 1)} s", ok)
    ok, _ = verdict_de("T9_panne", "ENF8_detection")
    ajoute("ENF8 — détection du nœud défaillant", "T9", f"alerte NOEUD_MUET après {fmt(t9.m('T9_detection_noeud_muet'), 0)} s", ok)
    ok, _ = verdict_de("ENF6_auth", "ENF6")
    ajoute("ENF6 — messages authentifiés", "ENF6 (11e nœud sans la clé)",
           f"{fmt(e6.m('ENF6_rejets_intrus'), 0)} rapports de l'intrus rejetés, {fmt(e6.m('ENF6_rejets_legitimes'), 0)} rapport légitime rejeté", ok)
    best = max([(2000.0 / (J[n].m(p + "_radio_on_capteurs_moy", 100) / 100 * 19 + 0.1) / 24, n)
                for n, p in [("E_energie_lpl", "E_lpl"), ("E_energie_lpl1024", "E_lpl1024"), ("E_energie_lpl2048", "E_lpl2048")]
                if J[n].existe] or [(0, "")])
    on = J["E_energie"].m("E_radio_on_capteurs_moy", 0)
    ajoute("ENF5 — autonomie ≥ 6 mois", "E_energie (PowerTracker)",
           f"radio toujours allumée : {fmt(on, 1)} % → {fmt(2000 / (on / 100 * 19 + 0.1) / 24, 0)} jours ; "
           f"meilleure variante LPL : {fmt(best[0], 0)} jours (estimation, voir § 5.6)", best[0] >= 182)
    ajoute("ENF4 / T10 — disponibilité ≥ 99,5 %", "—",
           "non mesurable en simulation (pas de pannes matérielles aléatoires) ; voir § 6", None)
    global BILAN
    BILAN = (sum(1 for l in lignes if "conforme" in l[3] and "non conforme" not in l[3]),
             sum(1 for l in lignes if "non conforme" in l[3]), sum(1 for l in lignes if l[3] == "—"))
    return tableau(["Exigence", "Test", "Valeur mesurée", "Verdict"], lignes, "exig")


def observation_routage():
    """Signale (d'après l'arbre mesuré) un nœud à portée du puits qui passe quand même par un relais."""
    gw, arbre, cas = NOEUDS[1], J["T6_reseau"].arbre, []
    for n, (parent, sauts) in sorted(arbre.items()):
        d = ((NOEUDS[n]["x"] - gw["x"]) ** 2 + (NOEUDS[n]["y"] - gw["y"]) ** 2) ** 0.5
        if d <= plan.PORTEE_COOJA and sauts >= 2:
            cas.append(f"{NOEUDS[n]['id']} (nœud {n}, à {fmt(d, 1)} m du puits) passe par {NOEUDS[parent]['id']}")
    if not cas:
        return ("<p>Dans cet essai, chaque nœud à portée du puits lui parle directement, et seuls P1, P2 et P3 "
                "passent par un relais. CTP choisit ses routes au démarrage d'après la qualité mesurée des liens et "
                "ne change de parent que si le gain dépasse un seuil (hystérésis) : selon les premiers paquets perdus, "
                "un nœud proche peut parfois rester sur un relais (observé lors d'essais précédents).</p>")
    return ("<p>Observation : " + " ; ".join(cas) + ". CTP fige son choix au démarrage et ne change de parent que si "
            "le gain dépasse un seuil (hystérésis), pour éviter les oscillations de route. Le coût est d'environ 10 ms "
            "par rapport.</p>")


def texte_energie():
    """Interprétation de la section énergie, construite à partir des valeurs mesurées."""
    cfg = [("E_energie", "E", "radio toujours allumée"), ("E_energie_lpl", "E_lpl", "LPL 512 ms"),
           ("E_energie_lpl1024", "E_lpl1024", "LPL 1024 ms"), ("E_energie_lpl2048", "E_lpl2048", "LPL 2048 ms")]
    val = [(lab, J[n].m(p + "_radio_on_capteurs_moy")) for n, p, lab in cfg if J[n].existe]
    val = [(lab, v) for lab, v in val if isinstance(v, float)]
    if not val:
        return "<p>(mesures d'énergie absentes)</p>"
    jours = lambda d: 2000.0 / (d / 100 * 19.0 + 0.1) / 24
    on = dict(val)
    lpl = [(lab, v) for lab, v in val if lab.startswith("LPL")]
    meilleur = min(lpl, key=lambda x: x[1]) if lpl else val[0]
    rejets = sum(1 for n, _, _ in cfg if J[n].existe for t, nn, m in J[n].lignes if m.startswith("ACQUIT_REJETE"))
    croissant = len(lpl) >= 2 and all(lpl[i][1] < lpl[i + 1][1] for i in range(len(lpl) - 1))
    t = f"""<p>Radio toujours allumée, la radio d'un capteur est active {fmt(on.get('radio toujours allumée', 0), 1)} % du
temps : environ {fmt(jours(on.get('radio toujours allumée', 100)), 0)} jours sur 2000 mAh. C'est l'argument du cahier contre
une écoute permanente (un ESP32 connecté en WiFi consomme encore davantage). L'écoute basse consommation (LPL) éteint la radio
et la rallume brièvement à intervalle fixe ; pour joindre un voisin endormi, l'émetteur répète son paquet pendant tout un
intervalle. Le meilleur réglage mesuré est <b>{meilleur[0]}</b> : radio active {fmt(meilleur[1], 1)} % du temps, soit environ
<b>{fmt(jours(meilleur[1]), 0)} jours</b> — {'au-delà' if jours(meilleur[1]) >= 182 else 'en deçà'} des 6 mois d'ENF5 avec ces hypothèses.</p>"""
    lat = [(lab, J[n].m(p + "_latence_max"), J[n].m(p + "_latence_p95")) for n, p, lab in cfg if J[n].existe]
    trop = [f"{lab} ({fmt(mx / 1000, 1)} s)" for lab, mx, _ in lat if isinstance(mx, float) and mx > 10000]
    ok10 = [lab for lab, mx, _ in lat if isinstance(mx, float) and mx <= 10000 and lab.startswith("LPL")]
    t += "<p><b>Latence :</b> "
    if ok10:
        t += "avec " + ", ".join(ok10) + ", la latence maximale reste sous les 10 s d'ENF1"
        p95 = dict((lab, v) for lab, _, v in lat)
        t += (f" (mais il faut {fmt(p95[ok10[0]] / 1000, 1)} s pour que 95 % des rapports arrivent, au-delà du budget d'1 s prévu pour "
              "le trajet nœud → passerelle : l'alerte arrive à temps, en consommant une plus grosse part du budget)") if isinstance(p95.get(ok10[0]), float) and p95[ok10[0]] > 1000 else ""
        t += ". "
    if trop:
        t += "En revanche " + ", ".join(trop) + " dépasse" + ("nt" if len(trop) > 1 else "") + " les 10 s : ces réglages sont incompatibles avec ENF1."
    t += "</p>"
    if croissant:
        t += """<p><b>Résultat contre-intuitif :</b> espacer les réveils (1024 puis 2048 ms) <i>augmente</i> la consommation.
Notre réseau diffuse beaucoup — balises de routage CTP, acquittements Drip répétés de proche en proche — et en LPL chaque
diffusion dure tout un intervalle de réveil. Au-delà de 512 ms, le coût des émissions dépasse l'économie d'écoute, et le canal
se sature (latence en secondes, plus de collisions). Pour viser 6 mois, il faut donc réduire les diffusions plutôt qu'allonger
le sommeil : acquittement toutes les 2 min en LPL (déjà fait), balises CTP plus espacées, rapports de vie moins fréquents.
Les nœuds de comptage et d'intrusion étant sur secteur d'après le plan, seuls les trois nœuds thermiques ont réellement
besoin de LPL.</p>"""
    t += f"""<div class="box warn"><b>Un piège découvert grâce à ces mesures.</b> En LPL, l'émulateur de la radio CC2420 produit
parfois des paquets incohérents (avertissement Cooja « packet size too large - repeating packet bytes ») dont le contrôle
CRC est pourtant valide. Un acquittement ainsi altéré disait « tout est reçu » : les capteurs effaçaient des données jamais
arrivées (taux de livraison tombé à 93 %). Depuis que la passerelle signe ses acquittements, ces faux messages sont rejetés
({rejets} rejets <code>ACQUIT_REJETE</code> sur les essais d'énergie). Artefact de simulation ou brouillage réel, la
leçon est la même : un message de contrôle doit être authentifié autant que les données.</div>
<p>Le taux de livraison des essais d'énergie est mesuré « à terme » (rapports publiés au moins 5 min avant la fin) : en LPL, un
rapport perdu n'est renvoyé qu'au cycle d'acquittement suivant, 2 min plus tard.</p>"""
    return t


# ============================================================================ page HTML
CSS = """
@page { size: A4; margin: 15mm 15mm 17mm; }
:root { --ink:#17293B; --muted:#5A6B7B; --rule:#CDD6DE; --code:#F1F4F6; --accent:#0E746D; --warn:#B4611A; --ok:#0E746D; --ko:#B3261E; }
* { box-sizing: border-box; }
html, body { background:#fff; }
body { margin:0 auto; max-width:190mm; padding:0 4mm; color:var(--ink); font:10.2pt/1.55 'IBM Plex Sans','Segoe UI',Arial,sans-serif; }
h1 { font:700 27pt/1.05 'Barlow Condensed','Arial Narrow',Arial,sans-serif; margin:10pt 0 6pt; }
h2 { font:700 16pt/1.2 'Barlow Condensed','Arial Narrow',Arial,sans-serif; margin:20pt 0 6pt; padding-top:7pt; border-top:1px solid var(--rule); break-after:avoid; }
h3 { font-size:10.6pt; margin:12pt 0 4pt; break-after:avoid; }
p, ul, ol { margin:0 0 7pt; }
ul, ol { padding-left:16pt; } li { margin-bottom:3pt; }
.eyebrow { font:500 8.5pt 'IBM Plex Mono',Consolas,monospace; letter-spacing:.1em; text-transform:uppercase; color:var(--muted); margin-top:6pt; }
.lead { font-size:11.3pt; }
pre { background:var(--code); border:1px solid var(--rule); border-radius:3px; padding:7pt 9pt; margin:0 0 2pt;
      font:8.4pt/1.45 'IBM Plex Mono',Consolas,monospace; white-space:pre-wrap; break-inside:avoid; }
code { font:8.8pt 'IBM Plex Mono',Consolas,monospace; background:var(--code); padding:0 3pt; border-radius:2px; }
pre code { background:none; padding:0; font-size:inherit; }
.src { font:7.8pt 'IBM Plex Mono',Consolas,monospace; color:var(--muted); margin:0 0 9pt; }
.box { border-left:3px solid var(--accent); background:#F3F8F7; padding:7pt 10pt; margin:0 0 9pt; break-inside:avoid; }
.box.warn { border-color:var(--warn); background:#FBF5EE; }
table { width:100%; border-collapse:collapse; margin:0 0 9pt; font-size:9pt; }
tr { break-inside:avoid; }
th, td { text-align:left; vertical-align:top; padding:4.5pt 6pt; border-bottom:1px solid var(--rule); }
th { font:600 7.6pt 'IBM Plex Mono',Consolas,monospace; letter-spacing:.06em; text-transform:uppercase; color:var(--muted); }
td.n, th.n { text-align:right; font-variant-numeric: tabular-nums; }
.exig td:nth-child(3) { font-variant-numeric: tabular-nums; }
.ok { color:var(--ok); font-weight:600; white-space:nowrap; } .ko { color:var(--ko); font-weight:600; white-space:nowrap; }
figure { margin:4pt 0 12pt; break-inside:avoid; }
figure img { width:100%; display:block; }
figcaption { font-size:8.6pt; color:var(--muted); margin-top:3pt; }
.flow { font:8.6pt/1.55 'IBM Plex Mono',Consolas,monospace; background:var(--code); border:1px solid var(--rule); padding:8pt 10pt; white-space:pre; overflow-x:auto; break-inside:avoid; margin-bottom:9pt; }
.kpis { display:grid; grid-template-columns:repeat(4,1fr); gap:6pt; margin:8pt 0 12pt; }
.kpi { border:1px solid var(--rule); border-radius:3px; padding:7pt 9pt; }
.kpi b { display:block; font:700 17pt/1.1 'Barlow Condensed','Arial Narrow',Arial,sans-serif; }
.kpi span { font-size:8.3pt; color:var(--muted); }
footer { margin-top:16pt; padding-top:6pt; border-top:1px solid var(--rule); font-size:8.3pt; color:var(--muted); }
@media (max-width: 640px) { body { padding:0 16px; } .kpis { grid-template-columns:repeat(2,1fr); } table { font-size:8.4pt; } }
"""


def page():
    figs = dict(topo=fig_topologie(), lat=fig_latence(), en=fig_energie(), t2=fig_t2(), t7=fig_t7())
    t6, t6b, t7, t9 = J["T6_reseau"], J["T6b_pertes"], J["T7_coupure"], J["T9_panne"]
    t_exig = exigences()
    nb_ok = sum(ok for j in J.values() for _, ok, _ in j.verdicts)
    nb_tot = sum(1 for j in J.values() for _ in j.verdicts)

    # Tableau du réseau : sauts et PDR par nœud (T6)
    lignes_res = []
    for n in range(2, 11):
        parent, sauts = t6.arbre.get(n, ("—", "—"))
        pdr = t6.m(f"T6_pdr_{n}")
        pdrb = t6b.m(f"T6b_pdr_{n}")
        lat = [l["ms"] for l in t6.latences() if l["src"] == n and not l["diff"]]
        lignes_res.append([f"{NOEUDS[n]['id']} ({n})", f"{NOEUDS[n]['x']} ; {NOEUDS[n]['y']}",
                           f'{parent} ({NOEUDS[parent]["id"]})' if parent in NOEUDS else "—",
                           f'<span class="n">{sauts}</span>',
                           fmt(sum(lat) / len(lat), 1) if lat else "—", fmt(max(lat), 0) if lat else "—",
                           fmt(pdr, 1, "%"), fmt(pdrb, 1, "%")])
    t_res = tableau(["Nœud", "x ; y (m)", "Parent CTP", "Sauts", "Latence moy. (ms)", "max (ms)", "PDR T6", "PDR T6b"], lignes_res)

    # Énergie par nœud
    lignes_en = []
    for n in range(1, 11):
        v = [J[nom].m(f"{p}_radio_on_{n}") for nom, p in [("E_energie", "E"), ("E_energie_lpl", "E_lpl"),
                                                        ("E_energie_lpl1024", "E_lpl1024"), ("E_energie_lpl2048", "E_lpl2048")]]
        lignes_en.append([f"{NOEUDS[n]['id']} ({n})"] + [fmt(x, 1, "%") for x in v])
    t_en = tableau(["Nœud", "Toujours allumée", "LPL 512 ms", "LPL 1024 ms", "LPL 2048 ms"], lignes_en)
    lat_lpl = [(lab, J[nom].m(p + "_latence_moy"), J[nom].m(p + "_latence_p95"), J[nom].m(p + "_latence_max"), J[nom].m(p + "_pdr_global"))
               for nom, p, lab in [("E_energie", "E", "toujours allumée"), ("E_energie_lpl", "E_lpl", "LPL 512 ms"),
                                   ("E_energie_lpl1024", "E_lpl1024", "LPL 1024 ms"), ("E_energie_lpl2048", "E_lpl2048", "LPL 2048 ms")]]
    t_lpl = tableau(["Radio", "Latence moy. (ms)", "95 % sous (ms)", "max (ms)", "Livraison à terme"],
                    [[a, fmt(b, 0), fmt(c, 0), fmt(d, 0), fmt(e, 2, "%")] for a, b, c, d, e in lat_lpl])

    # Les verdicts bruts, test par test
    lignes_v = []
    for nom, j in J.items():
        for v, ok, d in j.verdicts:
            lignes_v.append([f"<code>{esc(nom)}</code>", esc(v), esc(d), badge(ok)])
    t_v = tableau(["Journal", "Vérification", "Détail (tel qu'écrit par le script)", "Résultat"], lignes_v)

    corps = f"""
<div class="eyebrow">IFRI · Réseaux de capteurs sans fil &amp; IoT · Groupe 7 · rapport de simulation</div>
<h1>Surveillance d'une ligne de production : simulation TinyOS / Cooja</h1>
<p class="lead">Dix cartes simulées aux positions exactes du plan d'implantation, un réseau radio
multi-saut (CTP), des capteurs de température, de comptage et de présence, et une passerelle
qui produit les messages MQTT du cahier des charges. Chaque exigence vérifiable a son test
automatique ; toutes les valeurs de ce rapport sont extraites des journaux de ces tests.</p>

<div class="kpis">
  <div class="kpi"><b>{BILAN[0]} / {BILAN[0] + BILAN[1]}</b><span>exigences vérifiées conformes ({BILAN[1]} non conforme : ENF5 ; {BILAN[2]} non mesurable)</span></div>
  <div class="kpi"><b>{fmt(t6.m('T6_latence_moy'), 0)} ms</b><span>latence moyenne capteur → passerelle (T6)</span></div>
  <div class="kpi"><b>{fmt(t6.m('T6_pdr_global'), 1)} %</b><span>taux de livraison, 10 nœuds, 20 min</span></div>
  <div class="kpi"><b>{fmt(t7.m('T7_recuperation'), 0)} %</b><span>des rapports d'1 h de coupure récupérés</span></div>
</div>

<h2>1. Objectifs et correspondance réel ↔ simulation</h2>
<p>Le système réel (architecture du groupe) repose sur des ESP32 en WiFi et un Raspberry Pi
(Mosquitto, Node-RED, InfluxDB, Grafana). Cooja n'émule ni l'ESP32 ni le WiFi : il émule, instruction
par instruction, des cartes de réseau de capteurs. On garde donc ce qui fait la difficulté du
projet — la <b>géographie</b> de l'usine, les <b>rôles</b>, les <b>exigences temporelles</b> — et on
remplace le matériel par son équivalent « réseau de capteurs ».</p>
{tableau(["Dans l'usine", "Dans la simulation", "Pourquoi / conséquence"], [
    ["ESP32 + capteur", "Carte Sky (TelosB, MSP430 + radio CC2420), programmée en nesC / TinyOS", "Seule carte que TinyOS compile et que Cooja émule ; 10 Ko de RAM, 48 Ko de ROM"],
    ["WiFi 2,4 GHz, point d'accès", "IEEE 802.15.4 (250 kbit/s), modèle radio UDGM, portée 20 m", "Plus courte portée que le WiFi (30 m retenus) : impose le multi-saut, comme un vrai réseau de capteurs"],
    ["Raspberry Pi (passerelle + serveur)", "Nœud 1 : racine CTP, écrit sur son port série une ligne « topic + JSON » par message", "Le pont série → MQTT est la seule partie non simulée"],
    ["DS18B20 / thermocouple K", "Modèle thermique (montée en régime, dérive, bruit ± 0,3 °C)", "Scénario de surchauffe injectable (commande H)"],
    ["Barrière infrarouge FC-51", "Arrivées de pièces aléatoires (2 à 6 s), compteur en flash", "100 pièces injectables (commande +)"],
    ["PIR HC-SR501 + buzzer", "Détections aléatoires de jour, présence injectable (P), buzzer = LED bleue", "Horloge d'usine accélérée : 1 s = 1 min, départ 17h00"],
    ["Coupure réseau", "La passerelle est éloignée à 1 km pendant 1 h", "Coupure de la liaison sans arrêter la passerelle"],
    ["Nœud débranché", "Nœud retiré de la simulation (sim.removeMote)", "Panne franche, sans prévenir les voisins"],
])}
<div class="box warn"><b>Limites de la correspondance.</b> Les latences mesurées sont celles d'un réseau
802.15.4 non chargé, sans le trajet passerelle → broker → Node-RED → notification (budget
&lt; 3 + 3 + 2 s dans ENF1, non simulé). L'énergie est celle de la radio CC2420, pas d'un ESP32.
Le modèle UDGM est idéal (disque de portée, pas d'obstacle ni d'évanouissement) ; le test T6b
le dégrade volontairement. Les capteurs sont simulés : la précision de ± 1 °C (EF1) dépend du
composant réel (DS18B20 : ± 0,5 °C), pas du réseau.</div>

<h2>2. Architecture de la simulation</h2>
<h3>2.1 Quatre rôles, quatre programmes</h3>
<p>Une application nesC par rôle, avec un dossier <code>commun/</code> partagé. Cooja charge donc
quatre « types de cartes » ; chaque carte connaît son numéro (<code>TOS_NODE_ID</code>, écrit par
Cooja) et en déduit, grâce à <code>Plan.h</code> généré depuis le plan, son repère, sa machine et son seuil.</p>
{tableau(["Nœuds", "Programme", "Ce qu'il fait"], [
    ["1 (GW)", "<code>passerelle</code>", "Racine CTP ; vérifie l'authentification ; écrit topic + JSON ; alertes ; statistiques ; diffuse les acquittements"],
    ["2–4 (T1–T3)", "<code>thermique</code>", "Lecture toutes les 2 s, rapport toutes les 30 s, alerte immédiate au-delà du seuil de SA machine"],
    ["5–7 (C1–C3)", "<code>comptage</code>", "+1 à chaque pièce (sauvegarde en flash), rapport toutes les 30 s : cumul + cadence"],
    ["8–10 (P1–P3)", "<code>intrusion</code>", "Suit l'heure de l'usine ; de nuit, toute présence → alerte immédiate + buzzer ; rapport de vie toutes les 30 s"],
])}
<h3>2.2 Le message radio</h3>
<p>Le JSON du cahier des charges est trop gros et trop coûteux à émettre sur une radio basse
consommation. Les capteurs envoient une structure binaire de 23 octets ; c'est la passerelle qui
fabrique le JSON. Un exemple de ligne réellement écrite par la passerelle (test T6) :</p>
<pre><code>{esc(next((m for t, n, m in t6.lignes if n == 1 and m.startswith("RX src=4 ")), "RX ..."))}</code></pre>
{tableau(["Champ", "Taille", "Contenu"], [
    ["type, etat", "1 + 1 octet", "température / comptage / présence ; OK, ALERTE, FIN_ALERTE, VEILLE, ARME, INTRUSION"],
    ["source, seq", "2 + 2", "numéro du nœud et numéro de rapport (sert au taux de livraison et aux acquittements)"],
    ["age_ms", "4", "temps passé dans le tampon : la passerelle en déduit l'horodatage réel de la mesure"],
    ["valeur, compteur", "2 + 4", "dixièmes de °C · cadence et cumul de pièces · heure d'usine et nombre de détections"],
    ["parent, etx", "2 + 2", "le premier relais et le coût de route CTP : permet de dessiner l'arbre"],
    ["differe", "1", "1 si le rapport a attendu une coupure"],
    ["mac", "2", "code d'authentification calculé avec la clé du réseau (ENF6)"],
])}
<h3>2.3 Routage multi-saut (CTP) et acquittements de bout en bout (Drip)</h3>
<div class="flow">capteur ──PUB──> tampon ──CTP (saut par saut, accusé radio à chaque saut)──> passerelle ──> ligne MQTT
   ^                                                                            │
   └──────────── Drip : « nœud 8, j'ai tout reçu jusqu'au n° 41 » (toutes les 30 s) ┘</div>
<p><b>CTP</b> (Collection Tree Protocol, <code>tos/lib/net/ctp</code>) construit seul un arbre dont la
passerelle est la racine. Chaque nœud estime la qualité de ses liens (ETX : nombre moyen
d'émissions pour réussir un envoi) et choisit le voisin qui minimise le coût total jusqu'à la
racine. À 20 m de portée, P1 (22,7 m), P2 (26,2 m) et P3 (20,8 m) ne voient pas la passerelle :
leurs rapports passent par un relais.</p>
<p><b>Drip</b> (<code>tos/lib/net/drip</code>) fait le chemin inverse : il propage une valeur de la
passerelle vers tous les nœuds. On l'utilise pour un <b>acquittement de bout en bout</b> — l'équivalent
du QoS 1 de MQTT — car l'accusé de réception de CTP ne prouve que la réception par le voisin
(voir § 5.5 : sans lui, une coupure faisait perdre 100 % des données). L'acquittement est
<b>signé</b> par la passerelle avec la clé du réseau : un acquittement altéré ou falsifié ferait
effacer aux capteurs des données jamais reçues (voir § 5.6).</p>
<figure><img src="{figs['topo']}" alt="Plan de l'usine avec les 10 nœuds et les flèches de l'arbre de routage CTP, avant et après le retrait de T1">
<figcaption>Figure 1 — Positions du plan (mètres) et arbre CTP mesuré (flèche = « je confie mes paquets à »).
Le cercle pointillé est la portée de 20 m autour de la passerelle. À droite, après le retrait de T1, P1 passe par P2.</figcaption></figure>

<h2>3. Le code, pas à pas</h2>
<p>TinyOS est piloté par des <b>événements</b> : pas de boucle infinie, on écrit ce qu'il faut faire
quand « la carte a démarré », « la minuterie a sonné », « un paquet est arrivé ». Un composant
nesC a deux fichiers : une <b>configuration</b> (le câblage, avec des flèches <code>-&gt;</code>) et un
<b>module</b> (le comportement).</p>
<h3>3.1 Câbler une application : le nœud thermique</h3>
{extrait("thermique/ThermiqueAppC.nc", "configuration ThermiqueAppC", 17)}
<p>Le nœud thermique ne connaît ni la radio ni CTP : il utilise <code>PublicationC</code>, notre
service commun, et <code>ConsoleC</code> pour écrire du texte lisible dans Cooja.</p>
<h3>3.2 Lire le capteur et alerter tout de suite</h3>
{extrait("thermique/ThermiqueC.nc", "event void Lecture.fired()", 28)}
<p>La lecture locale toutes les 2 s ne coûte rien en radio. Sans elle, une surchauffe pourrait
attendre jusqu'à 30 s le rapport suivant, ce qui violerait ENF1.</p>
<h3>3.3 Ne rien perdre : tampon et acquittements</h3>
{extrait("commun/PublicationP.nc", "event void Acquit.changed()", 30)}
<h3>3.4 La passerelle : authentifier, dédoublonner, publier, alerter</h3>
{extrait("passerelle/PasserelleC.nc", "/* 1. Authentification", 21)}
<h3>3.5 Le compteur qui survit au redémarrage</h3>
{extrait("commun/FlashInterneC.nc", "/* IMPORTANT : pendant", 8)}
<p>Le compteur est écrit dans la mémoire flash interne du MSP430 à chaque pièce, et relu au démarrage.
mspsim reproduit fidèlement une contrainte du vrai matériel : une interruption pendant l'écriture
fait planter le microcontrôleur. D'où le bloc <code>atomic</code>.</p>
<h3>3.6 Un test automatique</h3>
{extrait("scenarios/tests/T2_surchauffe.js", "TIMEOUT(", 22)}
<p>Le script, exécuté par le plugin ScriptRunner de Cooja, reçoit chaque ligne écrite par chaque carte,
injecte des événements sur les ports série (<code>commander(3, "H")</code>), mesure les délais avec
l'horloge de Cooja (commune à tous les nœuds) et écrit ses verdicts.</p>

<h2>4. Les scénarios de test</h2>
{tableau(["Test", "Durée simulée", "Scénario"], [
    ["T1", "10 min", "fonctionnement normal ; on mesure l'écart entre rapports de chaque capteur"],
    ["T2", "4 min", "t = 120 s : sonde de M2 à 95 °C ; t = 160 s : retour normal ; t = 200 s : four M3 à 225 °C"],
    ["T4", "4 min", "C1 : arrêt des arrivées, remise à zéro, 100 pièces ; C2 : redémarrage forcé à t = 150 s"],
    ["T5", "16 min", "présences à 17h30 (P2), 19h00 (P1, P2, P3) et 08h30 le lendemain (P3)"],
    ["T6 / T6b", "20 min", "fonctionnement normal, 10 nœuds ; T6b : 80 % de réussite radio en limite de portée"],
    ["T7", "75 min", "t = 5 min : passerelle hors de portée pendant 1 h ; 10 min d'observation après le retour"],
    ["T9", "10 min", "t = 5 min : retrait du nœud T1, relais de P1"],
    ["ENF6", "5 min", "un 11e nœud, programmé avec une autre clé, posé près de T2"],
    ["Énergie", "4 × 15 min", "radio toujours allumée, puis écoute basse consommation (LPL) à 512, 1024, 2048 ms"],
])}

<h2>5. Résultats</h2>
<h3>5.1 Réseau : latence, sauts, taux de livraison (T6, T6b)</h3>
{t_res}
<figure><img src="{figs['lat']}" alt="Boîtes à moustaches de la latence par nombre de sauts, liens parfaits et dégradés">
<figcaption>Figure 2 — Latence capteur → passerelle de chaque rapport, par nombre de sauts. Les liens
dégradés provoquent des retransmissions (points isolés) mais aucune perte : CTP réémet jusqu'à 30 fois.</figcaption></figure>
<p>La latence mesurée inclut l'écriture de la ligne JSON sur le port série de la passerelle
(≈ 11 ms à 115 200 bit/s) : la part radio est encore plus faible. On est très loin du budget de
1 s du cahier pour le trajet nœud → passerelle.</p>
{observation_routage()}

<h3>5.2 Alertes de surchauffe (T2)</h3>
<figure><img src="{figs['t2']}" alt="Courbes de température des trois machines avec leurs seuils et les alertes">
<figcaption>Figure 3 — Températures rapportées (points = rapports, triangles = alertes de la passerelle).
Chaque machine a son seuil : le four tourne à 185 °C sans alerte.</figcaption></figure>
<p>De la mise à 95 °C à la ligne <code>ALERTE SURCHAUFFE MACHINE_02</code> :
<b>{fmt(J['T2_surchauffe'].m('T2_latence_injection_alerte_M2', 0) / 1000, 2)} s</b>, dont
{fmt(J['T2_surchauffe'].m('T2_latence_detection_alerte_M2', 0), 0)} ms entre la détection sur le nœud et l'alerte
— le reste est l'attente de la lecture suivante (au plus 2 s). Cible de 5 s tenue.</p>

<h3>5.3 Comptage et intrusion (T4, T5)</h3>
<p><b>T4</b> : après 100 pièces, le compteur local vaut {fmt(J['T4_comptage'].m('T4_compteur_local_C1'), 0)} et
la passerelle publie <code>"production_count":{fmt(J['T4_comptage'].m('T4_compteur_passerelle_C1'), 0)}</code>.
Le nœud C2, redémarré par son chien de garde à {fmt(J['T4_comptage'].m('T4_C2_avant_redemarrage'), 0)} pièces,
relit {fmt(J['T4_comptage'].m('T4_C2_restaure'), 0)} dans sa flash ; la passerelle détecte le redémarrage
(numéro de rapport revenu à 1).</p>
<p><b>T5</b> : de nuit, l'alerte arrive en {fmt(J['T5_intrusion'].m('T5_latence_ZONE_01', 0), 0)},
{fmt(J['T5_intrusion'].m('T5_latence_ZONE_02', 0), 0)} et {fmt(J['T5_intrusion'].m('T5_latence_ZONE_03', 0), 0)} ms
pour les zones 1, 2 et 3 (deux sauts chacune), avec le buzzer local. Les présences à 17h30 et à 08h30
ne déclenchent aucune alerte.</p>

<h3>5.4 Panne d'un relais et reconvergence (T9, ENF8)</h3>
{tableau(["Mesure (depuis le retrait de T1)", "Valeur"], [
    ["P1 choisit un nouveau parent", f"{fmt(t9.m('T9_reconvergence'), 1)} s — {esc(t9.mesures.get('T9_reconvergence', ('', ''))[1])}"],
    ["Premier rapport de P1 reçu par le nouveau chemin", f"{fmt(t9.m('T9_retablissement_P1'), 1)} s — {esc(t9.mesures.get('T9_retablissement_P1', ('', ''))[1])}"],
    ["La passerelle signale « NOEUD_MUET T1 »", f"{fmt(t9.m('T9_detection_noeud_muet'), 1)} s (seuil : 3 périodes + 5 s sans nouvelles)"],
    ["Taux de livraison des 8 autres capteurs après la panne", fmt(t9.m('T9_pdr_autres'), 1, "%")],
])}
<p>CTP ne détecte la panne qu'en essayant d'envoyer : P1 découvre l'absence de T1 à son rapport
suivant, épuise ses retransmissions, puis change de parent. Le rapport retardé n'est pas perdu : il
reste dans le tampon jusqu'à son acquittement.</p>

<h3>5.5 Coupure d'une heure (T7, ENF3)</h3>
<figure><img src="{figs['t7']}" alt="Occupation des tampons pendant la coupure et cumul des rapports reçus">
<figcaption>Figure 4 — En haut : rapports en attente dans le tampon de trois capteurs (1 par 30 s).
En bas : cumul des rapports reçus par la passerelle ; la marche au retour est le vidage des tampons.</figcaption></figure>
<p>{fmt(t7.m('T7_recuperes'), 0)} rapports sur {fmt(t7.m('T7_publies_pendant_coupure'), 0)} publiés pendant la
coupure ont été reçus après le retour, tous marqués <code>diff=1</code>, en {fmt(t7.m('T7_temps_vidage'), 0)} s.
Leur horodatage JSON est celui de la mesure, grâce au champ <code>age_ms</code> : écart maximal
{fmt(t7.m('T7_ecart_horodatage_max'), 1)} s. Le cahier ne fixant pas de tolérance, nous avons retenu ± 5 s (1/6 de la période :
une mesure ne peut pas être confondue avec sa voisine). L'écart restant est le temps passé dans les files des relais pendant le
vidage, que <code>age_ms</code> ne compte pas ; une horloge commune (synchronisation) l'éliminerait.</p>
<div class="box"><b>Ce que ce test nous a appris.</b> La première version perdait <b>100 %</b> des données
de la coupure. Quand la racine disparaît, aucun nœud ne le sait : chacun prend un voisin pour parent,
le coût de route gonfle sans fin (« comptage à l'infini », ETX de 20 à 12 000) et les paquets tournent
en boucle avant d'être jetés. L'accusé de réception de CTP était pourtant positif, puisque le voisin
avait bien reçu. Quatre corrections, chacune validée par un nouvel essai : (1) un acquittement de
bout en bout diffusé par la passerelle, et l'arrêt des émissions après 75 s sans acquittement ; (2) une balise de routage
forcée par la racine toutes les 30 s, sans quoi les nœuds ne la retrouvaient pas à son retour (une racine stable espace
ses balises jusqu'à plusieurs minutes) ; (3) au retour, les 9 capteurs vidaient leurs tampons en rafale et saturaient
les files des relais : le vidage est cadencé à un rapport toutes les 250 ms ; (4) la passerelle « abandonnait » les trous
de plus de 32 numéros et acquittait donc des rapports jamais reçus (57 % de pertes) : elle suit désormais une fenêtre de 160
numéros, plus grande que le tampon, et n'acquitte jamais un rapport qu'elle n'a pas reçu.</div>
<p>Capacité : le tampon garde 130 rapports, soit 65 min à 30 s. ENF3 demande 24 h, soit 2 880 rapports
(≈ 58 Ko) : il faudrait la flash externe de 1 Mo de la carte (<code>LogStorageC</code>), ou la mémoire
flash de l'ESP32 dans le prototype réel.</p>

<h3>5.6 Énergie (ENF5)</h3>
<figure><img src="{figs['en']}" alt="Pourcentage de radio allumée, autonomie estimée et latence pour quatre réglages de la radio">
<figcaption>Figure 5 — Mesures PowerTracker (15 min, 10 nœuds). Autonomie estimée pour 2000 mAh avec
19 mA radio allumée et 0,1 mA pour le microcontrôleur (hypothèses, pas des mesures).</figcaption></figure>
{t_lpl}
{t_en}
{texte_energie()}
<h3>5.7 Authentification (ENF6)</h3>
<p>Les {fmt(J['ENF6_auth'].m('ENF6_rapports_intrus'), 0)} rapports de l'intrus (même programme, autre clé)
— {fmt(J['ENF6_auth'].m('ENF6_rejets_intrus'), 0)} envois avec ses renvois, puisqu'il n'est jamais acquitté — sont tous rejetés (<code>REJET_AUTH</code>), et aucun rapport légitime ne l'est. Dans l'autre sens, un
nœud sans la clé rejette les acquittements de la passerelle : l'intrus du test est volontairement programmé pour passer
outre et émettre quand même. Le code
d'authentification est calculé par le capteur et vérifié par la passerelle : un relais ne peut pas
modifier un rapport sans être détecté.</p>

<h2>6. Exigences vérifiées</h2>
{t_exig}
<p><b>ENF4 (disponibilité ≥ 99,5 %, T10)</b> n'est pas mesurable en simulation : il faudrait des pannes
aléatoires sur une longue durée. La simulation en donne les briques : détection des nœuds muets,
reconvergence automatique (T9), stockage pendant les coupures (T7). <b>T3 et T8</b> (non rappelés dans
la consigne) ne sont pas traités.</p>
<h3>Détail de toutes les vérifications</h3>
{t_v}

<h2>7. Limites et perspectives</h2>
<ul>
<li><b>Prototype réel ESP32 + MQTT.</b> Les lignes de la passerelle contiennent déjà le topic et le JSON :
un pont série → <code>mosquitto_pub</code> suffit pour alimenter Node-RED, InfluxDB et Grafana. En WiFi, CTP
disparaît (le point d'accès joue la racine) mais le tampon et l'acquittement QoS 1 restent nécessaires.</li>
<li><b>Sécurité.</b> Le code d'authentification sur 16 bits est pédagogique (FNV-1a « salé »), sans
protection contre le rejeu ni chiffrement. En réel : AES-CCM matériel du CC2420 (802.15.4) ou TLS
sur MQTT (port 8883) avec un certificat par ESP32, et un compteur anti-rejeu.</li>
<li><b>Énergie.</b> Combiner LPL, une période de rapport adaptée (30 s seulement pour la température,
quelques minutes pour les rapports de vie) et un intervalle de balises CTP plus long. Les nœuds de
comptage et d'intrusion sont sur secteur (plan) : seuls les nœuds thermiques ont besoin de LPL.</li>
<li><b>Stockage 24 h.</b> Passer le tampon en flash externe (LogStorage) pour couvrir ENF3 en entier.</li>
<li><b>Heure d'usine.</b> Chaque nœud la calcule depuis son démarrage (écart ≤ 1 s entre nœuds dans
Cooja). En réel : NTP sur l'ESP32, ou l'heure de la passerelle diffusée par Drip.</li>
<li><b>Modèle radio.</b> UDGM est un disque parfait. Une étude plus réaliste utiliserait le modèle
MRM ou DGRM de Cooja avec les murs du plan.</li>
</ul>

<footer>Généré le {date.today().strftime('%d/%m/%Y')} par <code>rapport/generer_rapport.py</code> à partir de
<code>resultats/*.log</code>. Pour tout relancer : <code>bash tout_relancer.sh</code> dans WSL, puis
<code>python rapport/generer_rapport.py</code>. Code, scénarios et guide : <code>simulation/02_simulation_projet/README.md</code>.</footer>
"""
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rapport de simulation</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Mono:wght@400;500;600&family=Barlow+Condensed:wght@600;700&display=swap">
<style>{CSS}</style></head><body>{corps}</body></html>
"""


def main():
    manquants = [n for n, j in J.items() if not j.existe]
    if manquants:
        print("Attention, journaux absents :", ", ".join(manquants))
    sortie = ICI / "rapport_simulation.html"
    sortie.write_bytes(page().encode("utf-8"))
    print("OK :", sortie)
    chrome = next((c for c in [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                               r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]
                   if pathlib.Path(c).exists()), None)
    if chrome:
        pdf = ICI / "rapport_simulation.pdf"
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        "--virtual-time-budget=8000", f"--print-to-pdf={pdf}", sortie.as_uri()],
                       check=False, capture_output=True, timeout=180)
        print("OK :" if pdf.exists() else "PDF non produit :", pdf)


if __name__ == "__main__":
    main()
