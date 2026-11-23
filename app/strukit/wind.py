"""Wind velocity pressure, ASCE/SEI 7-22 Chapter 26.

Read from the standard (page images; numbers confirmed against the image):
  Eq. 26.10-1    qz = 0.00256 Kz Kzt Ke V^2 (psf; V in mi/h). qh is qz at the mean roof
                 height h. (In ASCE/SEI 7-22 the directionality factor Kd is applied with
                 the pressure coefficients, not in the velocity pressure.)
  Table 26.10-1  Kz and Kh for Exposures B, C and D, 0 to 500 ft; note 3: linear
                 interpolation between heights is acceptable. The 0.70 value for Exposure B
                 below 30 ft is for Chapter 28 only (the envelope procedure).
  Sect. 26.9, Table 26.9-1  Ke = e^(-0.0000362 ze), ze = ground elevation above sea level,
                 ft; Ke = 1.0 is permitted in all cases.
  Sect. 26.8     Kzt is entered by the engineer (1.0 where 26.8.1 does not apply).
Not covered here: pressure coefficients and design pressures (Chapters 27 to 30), Kd, G,
internal pressure.
"""
import math

HEIGHTS = (15, 20, 25, 30, 40, 50, 60, 70, 80, 90, 100, 120, 140, 160, 180, 200, 250, 300, 350, 400, 450, 500)
KZ = {"B": (0.57, 0.62, 0.66, 0.70, 0.74, 0.79, 0.83, 0.86, 0.90, 0.92, 0.95, 1.00, 1.04, 1.08, 1.11, 1.14, 1.21, 1.27, 1.33, 1.38, 1.42, 1.46),
      "C": (0.85, 0.90, 0.94, 0.98, 1.04, 1.09, 1.13, 1.17, 1.21, 1.24, 1.26, 1.31, 1.34, 1.39, 1.41, 1.44, 1.51, 1.57, 1.62, 1.66, 1.70, 1.74),
      "D": (1.03, 1.08, 1.12, 1.16, 1.22, 1.27, 1.31, 1.34, 1.38, 1.40, 1.43, 1.48, 1.52, 1.55, 1.58, 1.61, 1.68, 1.73, 1.78, 1.82, 1.86, 1.89)}


class WindError(ValueError):
    pass


def kz(exposure, z, chapter_28=False):
    if exposure not in KZ:
        raise WindError("wind: the exposure category must be B, C or D")
    if z is None or z < 0 or z > 500:
        raise WindError("wind: the height must be between 0 and 500 ft")
    t = KZ[exposure]
    if z <= 15:
        v = t[0]
    else:
        i = next(k for k in range(1, len(HEIGHTS)) if z <= HEIGHTS[k])
        v = t[i - 1] + (t[i] - t[i - 1]) * (z - HEIGHTS[i - 1]) / (HEIGHTS[i] - HEIGHTS[i - 1])
    if chapter_28 and exposure == "B" and z < 30:
        v = 0.70
    return v


def ke(elevation_ft):
    return math.exp(-0.0000362 * elevation_ft)


def velocity_pressure(V, exposure, z, Kzt=1.0, Ke=1.0, chapter_28=False):
    if V is None or V <= 0:
        raise WindError("wind: the basic wind speed must be a positive number")
    if Kzt is None or Kzt < 1.0:
        raise WindError("wind: Kzt is 1.0 or more")
    k = kz(exposure, z, chapter_28)
    return 0.00256 * k * Kzt * Ke * V ** 2, k
