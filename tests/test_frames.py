import numpy as np
from mission_framework.spacecraft.frames import julian_date_from_unix, eci_to_ecef, ecef_to_eci

def test_eci_ecef_roundtrip():
    t = 1700000000.0
    jd = julian_date_from_unix(t)
    r = np.array([7000e3, 0, 0])
    v = np.array([0, 7500.0, 0])

    r_ecef, v_ecef = eci_to_ecef(r, v, jd)
    r2, v2 = ecef_to_eci(r_ecef, v_ecef, jd)

    assert np.linalg.norm(r2 - r) < 1e-3
    assert np.linalg.norm(v2 - v) < 1e-6