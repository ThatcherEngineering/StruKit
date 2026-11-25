"""Shear lug under a column base plate, AISC Design Guide 1 (3rd Ed.) Sect. 4.3.3 and Example 4.7-5: concrete bearing on the lug and
concrete breakout of the lug (ACI 318-19 Sect. 17.11.2, 17.11.3, with 17.7.2), the lug in shear and flexure (AISC 360-22 Sect. J4.2, J4.5,
AISC Manual Eq. 9-1), the fillet welds of the lug to the plate, the anchor rod tension and the base plate bending from the eccentricity of
the shear (the large-moment base plate procedure of DG 1 Sect. 4.3.6, Eq. 4-32), and the least anchor embedment of ACI 318-19
17.11.1.1.8. Units: kips, inches, ksi."""
import math


class ShearLugError(ValueError):
    pass


def eccentric(V, P, e_in, N, B, fp, f):
    """Base plate under axial compression P (kips, + compression) and the moment V e: DG 1 Eq. 4-32 with qmax = fp B. Returns Y, T (total rod
    tension), q. f: plate centre to the tension rods."""
    q = fp * B
    M = V * e_in
    disc = (f + N / 2) ** 2 - 2 * (P * f + M) / q
    if disc < 0:
        raise ShearLugError("shear lug: the base plate is too small for the moment from the shear eccentricity (Eq. 4-32 has no solution)")
    Y = (f + N / 2) - math.sqrt(disc)
    return dict(M=M, q=q, Y=Y, T=max(q * Y - P, 0.0))


def concrete(fc_ksi, V, P_comp, bsl, tsl, hsl, ca1, ca2, ha, psi_c, lam=1.0, Abp=None, n_tension=0, Nsa=None):
    """ACI 318-19 limit states of the lug (LRFD, phi = 0.65 both): bearing 1.7 f'c Aef psi_brg (17.11.2.1, depth not over 2 tsl 17.11.2.1.1,
    psi_brg by Eq. 17.11.2.2.1) and breakout by 17.11.3 with 17.7.2: Avc the projected area less the lug's own bearing area, Avco = 4.5 ca1^2,
    Vb = 9 lambda (f'c)^0.5 ca1^1.5 (Eq. 17.7.2.2.1b), psi_ed,V (17.7.2.4), psi_h,V (17.7.2.6), psi_c,V as given."""
    hef = min(hsl, 2 * tsl)
    Aef = bsl * hef
    if P_comp > 0:
        psi_b = min(1 + 4 * P_comp / (Abp * fc_ksi), 2.0)
    elif P_comp < 0:
        psi_b = max(1 + P_comp / (n_tension * Nsa), 0.0) if (n_tension and Nsa) else 0.0
    else:
        psi_b = 1.0
    Vbrg = 1.7 * fc_ksi * Aef * psi_b
    c15 = 1.5 * ca1
    depth = min(hsl + c15, ha)
    width = bsl + 2 * min(c15, ca2)
    Avc = depth * width - hsl * bsl
    Avco = 4.5 * ca1 ** 2
    Vb = 9 * lam * math.sqrt(fc_ksi * 1000) * ca1 ** 1.5 / 1000
    psi_ed = 1.0 if ca2 >= c15 else 0.7 + 0.3 * ca2 / c15
    psi_h = max(math.sqrt(c15 / ha), 1.0) if ha < c15 else 1.0
    Vcb = Avc / Avco * psi_ed * psi_c * psi_h * Vb
    return dict(hef_brg=hef, Aef=Aef, psi_brg=psi_b, Vbrg=Vbrg, phiVbrg=0.65 * Vbrg, Avc=Avc, Avco=Avco, Vb=Vb, psi_ed=psi_ed, psi_h=psi_h, psi_c=psi_c,
                Vcb=Vcb, phiVcb=0.65 * Vcb, depth=depth, width=width)


def steel(Fy, Fu, bsl, tsl, weld, FEXX):
    """Nominal strengths of the lug at the plate: shear yielding 0.60 Fy Agv (J4-3), shear rupture 0.60 Fu Anv (J4-4), flexural yielding Fy Z
    and rupture Fu Z (J4.5), Z = b t^2 / 4; weld per inch Fnw Awe kds with kds = 1.5 (J2-4, J2-5) and the lever arm a = t + 2w/3."""
    Z = bsl * tsl ** 2 / 4
    return dict(Vy=0.60 * Fy * bsl * tsl, Vr=0.60 * Fu * bsl * tsl, My=Fy * Z, Mr=Fu * Z, Z=Z, a=tsl + 2 * weld / 3, rw=0.60 * FEXX * 0.7071 * weld * 1.5)
