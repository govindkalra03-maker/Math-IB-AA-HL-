"""IB Mathematics: analysis and approaches HL syllabus (first assessment 2021), as code -> name.

SL x.y codes are the common core, AHL x.y the additional higher level content. LEGACY codes
cover pre-2019 Mathematics HL content with no current equivalent; their middle number is the
topic they are filed under.
"""
import re

TOPICS = {
    1: "Number and Algebra",
    2: "Functions",
    3: "Geometry and Trigonometry",
    4: "Statistics and Probability",
    5: "Calculus",
}

SYLLABUS = {
    # ---- Topic 1: Number and algebra ------------------------------------------------------
    "SL 1.1": "Scientific notation (a × 10^k)",
    "SL 1.2": "Arithmetic sequences and series",
    "SL 1.3": "Geometric sequences and series",
    "SL 1.4": "Financial applications of geometric sequences",
    "SL 1.5": "Laws of exponents (integer); introduction to logarithms",
    "SL 1.6": "Simple deductive proof",
    "SL 1.7": "Laws of exponents (rational) and laws of logarithms",
    "SL 1.8": "Sum of an infinite geometric sequence",
    "SL 1.9": "Binomial theorem (natural n)",
    "AHL 1.10": "Counting principles (permutations and combinations); extended binomial theorem",
    "AHL 1.11": "Partial fractions",
    "AHL 1.12": "Complex numbers: Cartesian form and the Argand diagram",
    "AHL 1.13": "Complex numbers: modulus-argument (polar) and Euler forms",
    "AHL 1.14": "Complex roots of polynomials; De Moivre's theorem; powers and roots",
    "AHL 1.15": "Proof by induction, contradiction and counterexample",
    "AHL 1.16": "Systems of linear equations",
    # ---- Topic 2: Functions ---------------------------------------------------------------
    "SL 2.1": "Equations of straight lines",
    "SL 2.2": "Functions: domain, range, graph; inverse function",
    "SL 2.3": "Graphing functions",
    "SL 2.4": "Key features of graphs",
    "SL 2.5": "Composite functions; inverse functions",
    "SL 2.6": "The quadratic function",
    "SL 2.7": "Quadratic equations and inequalities; the discriminant",
    "SL 2.8": "Reciprocal and simple rational functions",
    "SL 2.9": "Exponential and logarithmic functions",
    "SL 2.10": "Solving equations analytically and graphically",
    "SL 2.11": "Transformations of graphs",
    "AHL 2.12": "Polynomial functions; factor and remainder theorems; sums and products of roots",
    "AHL 2.13": "Rational functions",
    "AHL 2.14": "Odd and even functions; self-inverse functions; restricted domains",
    "AHL 2.15": "Solving inequalities",
    "AHL 2.16": "Graphs of |f(x)|, f(|x|), 1/f(x), f(ax+b), [f(x)]²",
    # ---- Topic 3: Geometry and trigonometry -----------------------------------------------
    "SL 3.1": "3D geometry: distance, midpoint, volume and surface area; angles",
    "SL 3.2": "Trigonometry in triangles: sine rule, cosine rule, area",
    "SL 3.3": "Applications of trigonometry: bearings, elevation and depression",
    "SL 3.4": "The circle: radians, arc length, sector area",
    "SL 3.5": "Unit circle definitions; exact values",
    "SL 3.6": "Pythagorean identity; double angle identities",
    "SL 3.7": "Circular functions and their graphs",
    "SL 3.8": "Solving trigonometric equations",
    "AHL 3.9": "Reciprocal trigonometric ratios; inverse trigonometric functions",
    "AHL 3.10": "Compound angle identities; double angle for tan",
    "AHL 3.11": "Symmetry properties of trigonometric graphs",
    "AHL 3.12": "Vectors: concepts, components, algebra",
    "AHL 3.13": "Scalar product; angle between vectors",
    "AHL 3.14": "Vector equation of a line; kinematics with vectors",
    "AHL 3.15": "Intersecting, parallel and skew lines",
    "AHL 3.16": "Vector product; areas",
    "AHL 3.17": "Equations of a plane",
    "AHL 3.18": "Intersections and angles of lines and planes",
    # ---- Topic 4: Statistics and probability ----------------------------------------------
    "SL 4.1": "Sampling and data",
    "SL 4.2": "Presentation of data: histograms, cumulative frequency, box plots",
    "SL 4.3": "Measures of central tendency and dispersion",
    "SL 4.4": "Linear correlation and regression (y on x)",
    "SL 4.5": "Probability: sample spaces and events",
    "SL 4.6": "Venn and tree diagrams; combined, mutually exclusive and independent events",
    "SL 4.7": "Discrete random variables; expected value",
    "SL 4.8": "Binomial distribution",
    "SL 4.9": "Normal distribution",
    "SL 4.10": "Regression of x on y",
    "SL 4.11": "Conditional probability; testing for independence",
    "SL 4.12": "Standardisation of normal variables; inverse normal",
    "AHL 4.13": "Bayes' theorem",
    "AHL 4.14": "Continuous random variables; E(aX+b) and Var(aX+b)",
    # ---- Topic 5: Calculus ----------------------------------------------------------------
    "SL 5.1": "Limits; the derivative as gradient and rate of change",
    "SL 5.2": "Increasing and decreasing functions",
    "SL 5.3": "Derivative of axⁿ",
    "SL 5.4": "Tangents and normals",
    "SL 5.5": "Introduction to integration; area under a curve",
    "SL 5.6": "Standard derivatives; chain, product and quotient rules",
    "SL 5.7": "The second derivative",
    "SL 5.8": "Stationary points, optimisation and points of inflexion",
    "SL 5.9": "Kinematics",
    "SL 5.10": "Indefinite integrals of standard functions; integration by inspection",
    "SL 5.11": "Definite integrals; area between curves",
    "AHL 5.12": "Continuity, differentiability; first principles; higher derivatives",
    "AHL 5.13": "Limits at infinity; L'Hôpital's rule",
    "AHL 5.14": "Implicit differentiation; related rates",
    "AHL 5.15": "Derivatives and integrals of further functions (tan, sec, aˣ, arctan, …)",
    "AHL 5.16": "Integration by substitution and by parts",
    "AHL 5.17": "Area with the y-axis; volumes of revolution",
    "AHL 5.18": "Differential equations: Euler's method, separable, homogeneous, integrating factor",
    "AHL 5.19": "Maclaurin series",
    # ---- Pre-2019 Mathematics HL content with no current equivalent -----------------------
    "LEGACY 1.1": "Matrices (pre-2019 syllabus)",
    "LEGACY 4.1": "Poisson distribution (pre-2019 syllabus)",
}


def topic_of(code):
    """Topic number from a code: 'AHL 3.14' -> 3, 'LEGACY 4.1' -> 4."""
    return int(re.search(r"(\d+)\.\d+$", code).group(1))


def level_of(code):
    return code.split()[0]           # "SL", "AHL" or "LEGACY"


def sort_key(code):
    """Syllabus order: by topic, then section number; LEGACY after current content."""
    lvl, num = code.split()
    t, s = (int(x) for x in num.split("."))
    return (t, lvl == "LEGACY", s)


assert all(c in SYLLABUS for c in ("SL 1.2", "SL 2.1", "SL 3.3", "SL 2.10", "AHL 1.11"))
assert len([c for c in SYLLABUS if not c.startswith("LEGACY")]) == 9 + 7 + 11 + 5 + 8 + 10 + 12 + 2 + 11 + 8   # SL+AHL per topic
