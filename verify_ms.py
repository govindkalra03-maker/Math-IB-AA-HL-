"""Stage 5a — symbolic verification of every result used in the authored mark schemes
(May 2017 · Paper 1 · TZ2, which arrived without its scheme). author_ms.py imports this and
refuses to render if any check fails.

    .venv/bin/python -I verify_ms.py
"""
import sympy as sp
from sympy import (Interval, Rational, binomial, cos, diff, exp, expand, integrate, log, pi,
                   simplify, sin, solveset, sqrt, symbols, tan, sec, I, Abs, arg, S)

x, t, r, d, m, k, n, th, a, y, P = symbols("x t r d m k n theta a y P", real=True)


def same(u, v):
    return simplify(u - v) == 0


def q1():
    poly = expand((2 * x**2 + 1 / (2 * x**3))**10)
    const = poly.as_independent(x)[0]
    assert const == 840
    # general term exponent 20 - 5r = 0 -> r = 4, and C(10,4)*2^6*2^-4 = 840
    assert solveset(20 - 5 * r, r) == {4}
    assert binomial(10, 4) * 2**6 * Rational(1, 2**4) == 840


def q2():
    f = 2 * x**3 + 5
    assert f.subs(x, -2) == -11 and f.subs(x, 2) == 21
    assert all(diff(f, x).subs(x, v) >= 0 for v in (-2, -1, 0, 1, 2))      # increasing -> range [-11, 21]
    finv = sp.real_root((x - 5) / 2, 3)
    for v in (-11, -3, 5, 7, 21):                                            # f(f⁻¹(v)) = v on the domain
        assert same(f.subs(x, finv.subs(x, v)), v)
    assert finv.subs(x, -11) == -2 and finv.subs(x, 21) == 2


def q3():
    sol = solveset((9 + 3 * d)**2 - 9 * (9 + 7 * d), d)
    assert sol == {0, 1}                                                     # d ≠ 0 -> d = 1
    assert Rational(9 + 3, 9) == Rational(4, 3)
    assert Rational(9 + 7, 9 + 3) == Rational(4, 3)                          # 9, 12, 16 is geometric


def q4():
    s = t + cos(2 * t)
    v = diff(s, t)
    assert same(v, 1 - 2 * sin(2 * t))
    roots = sorted(solveset(v, t, Interval(0, 2 * pi)), key=lambda e: float(e))
    assert roots[:2] == [pi / 12, 5 * pi / 12]
    assert same(s.subs(t, pi / 12), pi / 12 + sqrt(3) / 2)


def q5():
    A, B = -1 + 4 * I, -3
    C, D = 1 - 2 * I, 3 + 2 * I
    sides = [B - A, C - B, D - C, A - D]
    assert len({sp.nsimplify(Abs(s)**2) for s in sides}) == 1                # equal sides
    turns = {simplify(sides[i + 1] / sides[i]) for i in range(3)}
    assert turns == {I}                                                      # every corner a right angle, same sense
    assert simplify((C - B) - (-I) * (A - B)) == 0                           # BC = BA rotated 90° clockwise (scheme's step)
    assert simplify(D - (A + (C - B))) == 0                                  # D = A + BC
    assert sp.im(C) < 0 and sp.re(D) > 0                                     # matches the diagram: C below, D right


def q6():
    lhs = integrate(1 / (x**2 + 1)**2, (x, 0, 1))
    integrand = (1 / (tan(th)**2 + 1)**2) * diff(tan(th), th)
    assert same(sp.trigsimp(integrand), cos(th)**2)
    rhs = integrate(cos(th)**2, (th, 0, pi / 4))
    assert same(lhs, rhs) and same(rhs, pi / 8 + Rational(1, 4))
    assert same(diff(th / 2 + sin(2 * th) / 4, th), cos(th)**2)


def q7():
    msol = solveset(1 - exp(-m) - Rational(3, 4), m, S.Reals)
    assert msol == {log(4)}
    lam = 2 * log(4)
    p = 1 - exp(-lam) * (1 + lam)
    assert same(p, (15 - log(16)) / 16)
    assert same(lam, log(16))


def q8():
    assert binomial(2, 2) == binomial(3, 3) == 1                            # base case n = 3
    kk = symbols("k", integer=True, positive=True)
    step = sp.expand_func(binomial(kk, 3) + binomial(kk, 2) - binomial(kk + 1, 3))
    assert simplify(step) == 0
    assert same(kk * (kk - 1) * (kk - 2) / 6 + kk * (kk - 1) / 2, (kk + 1) * kk * (kk - 1) / 6)
    for N in range(3, 30):                                                   # numerical sanity check
        assert sum(binomial(j, 2) for j in range(2, N)) == binomial(N, 3)


def q9():
    ap = symbols("a", positive=True)
    f = x**2 - ap**2
    assert solveset(f, x, S.Reals) == {-ap, ap} and f.subs(x, 0) == -ap**2
    h = 1 / f
    assert diff(h, x).subs(x, 0) == 0 and same(diff(h, x, 2).subs(x, 0), -2 / ap**4)   # local max
    assert same(h.subs(x, 0), -1 / ap**2)
    assert sp.limit(h, x, sp.oo) == 0 and sp.limit(h, x, ap, "+") == sp.oo and sp.limit(h, x, ap, "-") == -sp.oo
    F = (x**2 - ap**2 - 2) * sin(x) + 2 * x * cos(x)
    assert same(diff(F, x), f * cos(x))
    assert same(integrate(2 * x * sin(x), x), -2 * x * cos(x) + 2 * sin(x))
    g = x * sqrt(f)
    assert same(diff(g, x), (2 * x**2 - ap**2) / sqrt(f))
    for v in (1.01, 2, 5, -1.01, -3):                                        # g' > 0 for |x| > a (a = 1)
        assert float(((2 * x**2 - 1) / sqrt(x**2 - 1)).subs(x, v)) > 0


def q10():
    h = (P - 2 * r - pi * r) / 2
    A = 2 * r * h + pi * r**2 / 2
    assert same(A, P * r - 2 * r**2 - pi * r**2 / 2)
    dA = diff(A, r)
    assert same(dA, P - 4 * r - pi * r)
    rstar = solveset(dA, r).args[0]
    assert same(rstar, P / (4 + pi)) and same(2 * rstar, 2 * P / (4 + pi))
    assert same(diff(A, r, 2), -(4 + pi))
    assert same(h.subs(r, rstar), rstar)


def q11():
    eq = 2 * sin(x + pi / 3) - cos(x + pi / 6)
    assert solveset(eq, x, Interval(0, pi)) == {5 * pi / 6}                  # 150°
    assert same(sp.expand_trig(2 * sin(x + pi / 3)), sin(x) + sqrt(3) * cos(x))
    s105, c105 = sin(7 * pi / 12), cos(7 * pi / 12)
    assert same(s105, (sqrt(6) + sqrt(2)) / 4) and same(c105, (sqrt(2) - sqrt(6)) / 4)
    assert same(s105 + c105, 1 / sqrt(2))
    z = 1 - cos(2 * th) - I * sin(2 * th)
    polar = 2 * sin(th) * (cos(th - pi / 2) + I * sin(th - pi / 2))
    assert same(sp.expand(sp.expand_trig(z - polar)), 0)
    for v in (0.3, 1.0, 1.57, 2.5, 3.0):                                     # modulus and argument on (0, π)
        zv = complex(z.subs(th, v))
        assert abs(abs(zv) - 2 * float(sin(v))) < 1e-12
        assert abs(sp.arg(sp.nsimplify(zv)).evalf() - (v - float(pi) / 2)) < 1e-9
    for shift in (-pi / 6, pi / 2, 7 * pi / 6):                              # the three cube roots
        w = sp.cbrt(2 * sin(th)) * exp(I * (th / 3 + shift))
        for v in (0.4, 1.3, 2.7):
            assert abs(complex((w**3).subs(th, v)) - complex(z.subs(th, v))) < 1e-9


CHECKS = [q1, q2, q3, q4, q5, q6, q7, q8, q9, q10, q11]


def run():
    for fn in CHECKS:
        fn()
        print(f"  verified {fn.__name__}")
    return True


if __name__ == "__main__":
    run()
    print("all results verified")
