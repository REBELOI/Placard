"""Generateur d'icone pour PlacardCAD / REB & ELOI."""

from PIL import Image, ImageDraw, ImageFont
import os

SIZE = 256
PAD = 20


def generer_icone(taille: int = SIZE) -> Image.Image:
    """Genere une icone representant un placard avec compartiments et rayons."""
    img = Image.new("RGBA", (taille, taille), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Fond arrondi (bleu fonce)
    r = 40
    fond = (45, 62, 80)  # bleu-gris fonce
    draw.rounded_rectangle([4, 4, taille - 5, taille - 5], radius=r, fill=fond)

    # Zone placard (rectangle interieur)
    mx, my = PAD + 10, PAD + 8
    pw = taille - 2 * mx
    ph = taille - 2 * my - 20  # marge bas pour texte

    # Contour placard (bois clair)
    bois = (210, 180, 140)
    bois_fonce = (160, 130, 90)
    blanc = (245, 240, 232)

    # Murs (epaisseur)
    ep = 8
    # Mur gauche
    draw.rectangle([mx, my, mx + ep, my + ph], fill=bois)
    # Mur droit
    draw.rectangle([mx + pw - ep, my, mx + pw, my + ph], fill=bois)
    # Plafond
    draw.rectangle([mx, my, mx + pw, my + ep], fill=bois)
    # Sol
    draw.rectangle([mx, my + ph - ep, mx + pw, my + ph], fill=bois_fonce)

    # Interieur
    ix = mx + ep
    iy = my + ep
    iw = pw - 2 * ep
    ih = ph - 2 * ep
    draw.rectangle([ix, iy, ix + iw, iy + ih], fill=blanc)

    # Rayon haut (barre horizontale pleine largeur)
    rh_h = 6
    rh_y = iy + 20
    draw.rectangle([ix, rh_y, ix + iw, rh_y + rh_h], fill=bois)

    # Separation centrale (panneau vertical sous rayon haut)
    sep_w = 5
    sep_x = ix + iw // 2 - sep_w // 2
    draw.rectangle([sep_x, rh_y + rh_h, sep_x + sep_w, iy + ih], fill=bois)

    # Rayons compartiment gauche (3 rayons)
    zone_y_haut = rh_y + rh_h
    zone_y_bas = iy + ih
    zone_h = zone_y_bas - zone_y_haut
    nb_rayons_g = 3
    rayon_h = 4
    for i in range(1, nb_rayons_g + 1):
        ry = zone_y_haut + i * zone_h // (nb_rayons_g + 1)
        draw.rectangle([ix + 2, ry, sep_x - 2, ry + rayon_h], fill=bois)

    # Rayons compartiment droit (2 rayons)
    nb_rayons_d = 2
    for i in range(1, nb_rayons_d + 1):
        ry = zone_y_haut + i * zone_h // (nb_rayons_d + 1)
        draw.rectangle([sep_x + sep_w + 2, ry, ix + iw - 2, ry + rayon_h], fill=bois)

    # Cremailleres (petits traits verticaux sur les bords de la separation)
    crem_color = (120, 120, 120)
    crem_w = 3
    # Gauche de la separation
    for i in range(zone_y_haut + 8, zone_y_bas - 4, 8):
        draw.rectangle([sep_x - crem_w, i, sep_x, i + 2], fill=crem_color)
    # Droite de la separation
    for i in range(zone_y_haut + 8, zone_y_bas - 4, 8):
        draw.rectangle([sep_x + sep_w, i, sep_x + sep_w + crem_w, i + 2],
                        fill=crem_color)
    # Mur gauche interieur
    for i in range(zone_y_haut + 8, zone_y_bas - 4, 8):
        draw.rectangle([ix, i, ix + crem_w, i + 2], fill=crem_color)
    # Mur droit interieur
    for i in range(zone_y_haut + 8, zone_y_bas - 4, 8):
        draw.rectangle([ix + iw - crem_w, i, ix + iw, i + 2], fill=crem_color)

    # Tasseaux sous rayon haut (petits triangles)
    tass_color = bois_fonce
    tass_size = 8
    # Tasseau gauche
    tx = ix + 2
    draw.polygon([(tx, rh_y + rh_h), (tx + tass_size, rh_y + rh_h),
                  (tx, rh_y + rh_h + tass_size)], fill=tass_color)
    # Tasseau central gauche
    tx = sep_x - 2
    draw.polygon([(tx, rh_y + rh_h), (tx - tass_size, rh_y + rh_h),
                  (tx, rh_y + rh_h + tass_size)], fill=tass_color)
    # Tasseau central droit
    tx = sep_x + sep_w + 2
    draw.polygon([(tx, rh_y + rh_h), (tx + tass_size, rh_y + rh_h),
                  (tx, rh_y + rh_h + tass_size)], fill=tass_color)
    # Tasseau droit
    tx = ix + iw - 2
    draw.polygon([(tx, rh_y + rh_h), (tx - tass_size, rh_y + rh_h),
                  (tx, rh_y + rh_h + tass_size)], fill=tass_color)

    # Texte "R&E" en bas
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    except (OSError, IOError):
        font = ImageFont.load_default()
    text = "R&E"
    text_color = (230, 220, 200)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    tx = (taille - tw) // 2
    ty = my + ph + 2
    draw.text((tx, ty), text, fill=text_color, font=font)

    return img


def main():
    """Genere les icones en plusieurs tailles."""
    out_dir = os.path.dirname(os.path.abspath(__file__))

    # PNG 256x256
    icon = generer_icone(256)
    icon.save(os.path.join(out_dir, "icon_256.png"))

    # PNG 64x64
    icon_64 = generer_icone(256).resize((64, 64), Image.LANCZOS)
    icon_64.save(os.path.join(out_dir, "icon_64.png"))

    # PNG 128x128
    icon_128 = generer_icone(256).resize((128, 128), Image.LANCZOS)
    icon_128.save(os.path.join(out_dir, "icon_128.png"))

    # ICO (multi-taille)
    icon_ico = generer_icone(256)
    icon_ico.save(
        os.path.join(out_dir, "icon.ico"),
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    )

    print("Icones generees dans", out_dir)


if __name__ == "__main__":
    main()
