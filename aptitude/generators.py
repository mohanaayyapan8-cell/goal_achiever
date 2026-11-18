"""Computed aptitude questions. Each generator calculates its own answer, so the key is always
consistent with the question. Output is deterministic (fixed seeds) so the bank never changes by surprise."""
import math
import random
from fractions import Fraction

PER_TOPIC = 10


def _shuffled(rng, correct, wrongs):
    options = [correct] + list(wrongs)
    rng.shuffle(options)
    return options, options.index(correct)


def _num_wrongs(rng, correct, step, ok=lambda v: v > 0):
    cands = {correct + d for d in (step, -step, 2 * step, -2 * step, 3 * step, max(1, step // 2), -max(1, step // 2))}
    cands = sorted(c for c in cands if c != correct and ok(c))
    k = 1
    while len(cands) < 3:
        cands.append(correct + 4 * step + k)
        k += 1
    return rng.sample(cands, 3)


def _num_q(rng, topic, stem, correct, step, expl, fmt="{}", ok=lambda v: v > 0):
    wrongs = _num_wrongs(rng, correct, step, ok)
    opts, idx = _shuffled(rng, fmt.format(correct), [fmt.format(w) for w in wrongs])
    return {"topic": topic, "stem": stem, "options": opts, "correct": idx, "explanation": expl}


def _frac(f):
    return f"{f.numerator}/{f.denominator}" if f.denominator != 1 else str(f.numerator)


def _frac_q(rng, topic, stem, correct, expl):
    a, b = correct.numerator, correct.denominator
    cands = {Fraction(a + 1, b), Fraction(a, b + 1), Fraction(a, b + 2), Fraction(max(b - a, 1), b), Fraction(1, b + 1),
             Fraction(a + 2, b + 3), Fraction(1, 2), Fraction(1, 3)}
    cands = sorted((c for c in cands if c != correct and 0 < c <= 1), key=lambda c: (c.denominator, c.numerator))
    wrongs = rng.sample(cands, 3)
    opts, idx = _shuffled(rng, _frac(correct), [_frac(w) for w in wrongs])
    return {"topic": topic, "stem": stem_clean(stem), "options": opts, "correct": idx, "explanation": expl}


def stem_clean(s):
    return " ".join(s.split())


def gen_percentages(rng):
    t, out = "Percentages", []
    for i in range(PER_TOPIC):
        kind = i % 4
        if kind == 0:
            p = rng.choice([10, 12, 15, 20, 25, 30, 35, 40, 45, 60, 75])
            n = rng.choice([x for x in range(40, 501, 20) if x * p % 100 == 0])
            ans = n * p // 100
            out.append(_num_q(rng, t, f"What is {p}% of {n}?", ans, max(2, ans // 8), f"{p}% of {n} = {p}/100 × {n} = {ans}."))
        elif kind == 1:
            p = rng.choice([10, 20, 25, 50])
            b = rng.choice(range(40, 401, 20))
            m = b * (100 + p) // 100
            out.append(_num_q(rng, t, f"A number increased by {p}% becomes {m}. What is the number?", b, max(5, b // 8),
                              f"Let the number be x. x × (100+{p})/100 = {m}, so x = {m} × 100 / {100 + p} = {b}."))
        elif kind == 2:
            n = rng.choice([20, 25, 40, 50, 80, 100, 200])
            a = rng.choice([x for x in range(1, n) if x * 100 % n == 0 and x * 100 // n >= 10])
            ans = a * 100 // n
            out.append(_num_q(rng, t, f"{a} out of {n} students passed an exam. What is the pass percentage?", ans, 5,
                              f"Percentage = {a}/{n} × 100 = {ans}%.", "{}%"))
        else:
            x = rng.choice([100, 200, 250, 400, 500, 800])
            inc = rng.choice([10, 20, 25, 40, 50])
            y = x * (100 + inc) // 100
            out.append(_num_q(rng, t, f"The price of an item rises from Rs. {x} to Rs. {y}. What is the percentage increase?", inc, 5,
                              f"Increase = {y} − {x} = {y - x}. Percentage increase = {y - x}/{x} × 100 = {inc}%.", "{}%"))
    return out


def gen_profit_loss(rng):
    t, out = "Profit and Loss", []
    for i in range(PER_TOPIC):
        kind = i % 4
        if kind == 0:
            cp, p = rng.choice([(c, p) for c in (200, 250, 400, 500, 800, 1000, 1200, 1500) for p in (10, 12, 15, 20, 25) if c * p % 100 == 0])
            sp = cp * (100 + p) // 100
            out.append(_num_q(rng, t, f"An article bought for Rs. {cp} is sold at a profit of {p}%. What is the selling price (in Rs.)?", sp,
                              max(10, sp // 10), f"SP = CP × (100 + {p})/100 = {cp} × {100 + p}/100 = {sp}."))
        elif kind == 1:
            cp = rng.choice([200, 400, 500, 800, 1000, 1200])
            p = rng.choice([5, 10, 15, 20, 25, 30])
            sp = cp * (100 + p) // 100
            out.append(_num_q(rng, t, f"An article costing Rs. {cp} is sold for Rs. {sp}. What is the profit percentage?", p, 5,
                              f"Profit = {sp} − {cp} = {sp - cp}. Profit % = {sp - cp}/{cp} × 100 = {p}%.", "{}%"))
        elif kind == 2:
            cp = rng.choice([400, 500, 800, 1000, 1200, 2000])
            loss = rng.choice([10, 20, 25])
            sp = cp * (100 - loss) // 100
            out.append(_num_q(rng, t, f"A seller loses {loss}% by selling an item for Rs. {sp}. What is its cost price (in Rs.)?", cp,
                              max(20, cp // 10), f"SP = CP × (100 − {loss})/100, so CP = {sp} × 100/{100 - loss} = {cp}."))
        else:
            mp, d = rng.choice([(m, d) for m in (500, 800, 1000, 1200, 2000) for d in (10, 20, 25, 30) if m * d % 100 == 0])
            sp = mp * (100 - d) // 100
            out.append(_num_q(rng, t, f"The marked price of a shirt is Rs. {mp}. After a discount of {d}%, what is the selling price (in Rs.)?", sp,
                              max(10, sp // 10), f"Discount = {d}% of {mp} = {mp * d // 100}. SP = {mp} − {mp * d // 100} = {sp}."))
    return out


def gen_interest(rng):
    t, out = "Simple and Compound Interest", []
    for i in range(PER_TOPIC):
        kind = i % 4
        if kind == 0:
            P, R, T = rng.choice([1000, 2000, 2500, 4000, 5000, 8000]), rng.choice([5, 6, 8, 10, 12]), rng.choice([2, 3, 4, 5])
            si = P * R * T // 100
            out.append(_num_q(rng, t, f"What is the simple interest on Rs. {P} at {R}% per annum for {T} years (in Rs.)?", si, max(10, si // 8),
                              f"SI = P × R × T / 100 = {P} × {R} × {T} / 100 = {si}."))
        elif kind == 1:
            P, R, T = rng.choice([1000, 2000, 5000, 8000]), rng.choice([4, 5, 6, 8, 10]), rng.choice([2, 3, 4, 5])
            A = P + P * R * T // 100
            out.append(_num_q(rng, t, f"Rs. {P} amounts to Rs. {A} in {T} years at simple interest. What is the rate per annum?", R, 1,
                              f"SI = {A} − {P} = {A - P}. R = SI × 100 / (P × T) = {A - P} × 100 / ({P} × {T}) = {R}%.", "{}%"))
        elif kind == 2:
            P, R = rng.choice([(p, r) for p in (1600, 2000, 4000, 5000, 8000, 10000, 20000) for r in (5, 10, 20)
                               if (Fraction(p) * ((100 + r) ** 2 - 10000) / 10000).denominator == 1])
            ci = int(Fraction(P) * ((100 + R) ** 2 - 10000) / 10000)
            out.append(_num_q(rng, t, f"What is the compound interest on Rs. {P} at {R}% per annum for 2 years (in Rs.)?", ci, max(10, ci // 8),
                              f"Amount = {P} × (1 + {R}/100)² = {P + ci}. CI = {P + ci} − {P} = {ci}."))
        else:
            R = rng.choice([5, 10, 20, 25])
            years = 100 // R
            out.append(_num_q(rng, t, f"At what time (in years) will a sum of money double itself at {R}% simple interest per annum?", years, 2,
                              f"Interest needed = the principal itself, so {R} × T / 100 = 1 and T = 100/{R} = {years} years.", "{}"))
    return out


def gen_time_work(rng):
    t, out = "Time and Work", []
    pairs = [(12, 12), (10, 15), (20, 30), (6, 12), (15, 30), (12, 24), (30, 45), (10, 40), (20, 60), (8, 24)]
    for i in range(PER_TOPIC):
        kind = i % 3
        if kind == 0:
            a, b = pairs[i % len(pairs)]
            ans = a * b // (a + b)
            out.append(_num_q(rng, t, f"A can finish a job in {a} days and B can finish it in {b} days. Working together, how many days will they take?",
                              ans, 2, f"Together in one day they do 1/{a} + 1/{b} = {a + b}/{a * b} of the job, so they need {a * b}/{a + b} = {ans} days."))
        elif kind == 1:
            a = rng.choice([8, 10, 12, 15, 20, 24])
            d = rng.choice([x for x in range(2, a) if True])
            f = Fraction(d, a)
            correct = Fraction(d, a)
            wrongs = [Fraction(a - d, a), Fraction(d, a + d), Fraction(d + 1, a)]
            wrongs = [w for w in dict.fromkeys(wrongs) if w != correct and 0 < w <= 1]
            while len(wrongs) < 3:
                wrongs.append(Fraction(len(wrongs) + 1, a + 7))
            wrongs = [w for w in dict.fromkeys(wrongs) if w != correct][:3]
            opts, idx = _shuffled(rng, _frac(correct), [_frac(w) for w in wrongs])
            out.append({"topic": t, "stem": f"A can complete a piece of work in {a} days. What fraction of the work does A complete in {d} days?",
                        "options": opts, "correct": idx, "explanation": f"In one day A does 1/{a}, so in {d} days A does {d}/{a} = {_frac(f)} of the work."})
        else:
            m1, d1 = rng.choice([6, 8, 10, 12, 15]), rng.choice([10, 12, 15, 20, 24])
            total = m1 * d1
            m2 = rng.choice([m for m in (4, 5, 6, 8, 10, 12, 15, 20, 24, 30, 40) if total % m == 0 and m != m1])
            out.append(_num_q(rng, t, f"{m1} men can complete a job in {d1} days. In how many days can {m2} men complete the same job?",
                              total // m2, 2, f"Total work = {m1} × {d1} = {total} man-days. Days for {m2} men = {total}/{m2} = {total // m2}."))
    return out


def gen_speed(rng):
    t, out = "Speed, Time and Distance", []
    for i in range(PER_TOPIC):
        kind = i % 4
        if kind == 0:
            s, h = rng.choice([40, 45, 50, 60, 72, 80]), rng.choice([2, 3, 4, 5])
            out.append(_num_q(rng, t, f"A car travels at {s} km/h for {h} hours. What distance does it cover (in km)?", s * h, max(5, s // 2),
                              f"Distance = speed × time = {s} × {h} = {s * h} km."))
        elif kind == 1:
            s1, s2 = rng.choice([(40, 60), (30, 60), (20, 30), (60, 90), (30, 45), (50, 75)])
            avg = 2 * s1 * s2 // (s1 + s2)
            out.append(_num_q(rng, t, f"A man goes to a place at {s1} km/h and returns by the same road at {s2} km/h. What is his average speed for the whole trip (in km/h)?",
                              avg, 4, f"Average speed for equal distances = 2ab/(a+b) = 2 × {s1} × {s2}/({s1}+{s2}) = {avg} km/h."))
        elif kind == 2:
            s = rng.choice([36, 54, 72, 90, 108])
            sec = rng.choice([6, 8, 10, 12, 15])
            ms = s * 5 // 18
            length = ms * sec
            out.append(_num_q(rng, t, f"A train {length} m long runs at {s} km/h. How many seconds does it take to cross a pole?", sec, 2,
                              f"Speed = {s} × 5/18 = {ms} m/s. Time = length/speed = {length}/{ms} = {sec} s."))
        else:
            k = rng.choice([18, 36, 54, 72, 90, 108])
            out.append(_num_q(rng, t, f"Convert {k} km/h into m/s.", k * 5 // 18, 2, f"Multiply by 5/18: {k} × 5/18 = {k * 5 // 18} m/s."))
    return out


def gen_ratio(rng):
    t, out = "Ratios and Proportions", []
    for i in range(PER_TOPIC):
        kind = i % 4
        if kind == 0:
            a, b = rng.choice([(2, 3), (3, 5), (4, 5), (1, 4), (3, 7), (5, 7)])
            total = (a + b) * rng.choice([10, 20, 30, 40, 50])
            share = total * max(a, b) // (a + b)
            out.append(_num_q(rng, t, f"Rs. {total} is divided between two people in the ratio {a}:{b}. What is the larger share (in Rs.)?", share, max(10, share // 8),
                              f"Total parts = {a + b}. One part = {total}/{a + b} = {total // (a + b)}. Larger share = {max(a, b)} × {total // (a + b)} = {share}."))
        elif kind == 1:
            a, b, c, d = rng.choice([(2, 3, 4, 5), (1, 2, 3, 4), (3, 4, 2, 3), (2, 5, 5, 6), (3, 2, 4, 5)])
            x, y = a * c, b * d
            g = math.gcd(x, y)
            correct = f"{x // g}:{y // g}"
            wrongs = [f"{a}:{d}", f"{x // g + 1}:{y // g}", f"{b}:{c}", f"{y // g}:{x // g}"]
            wrongs = [w for w in dict.fromkeys(wrongs) if w != correct][:3]
            opts, idx = _shuffled(rng, correct, wrongs)
            out.append({"topic": t, "stem": f"If A:B = {a}:{b} and B:C = {c}:{d}, what is A:C?", "options": opts, "correct": idx,
                        "explanation": f"Make B equal: A:B:C = {a}×{c} : {b}×{c} : {b}×{d} = {x}:{b * c}:{y}. So A:C = {x}:{y} = {correct}."})
        elif kind == 2:
            u = rng.choice([3, 4, 5, 6, 8, 10])
            x, y = rng.choice([(6, 9), (10, 15), (12, 20), (5, 8), (4, 7)])
            out.append(_num_q(rng, t, f"If {x} pencils cost Rs. {u * x}, how much do {y} pencils cost (in Rs.)?", u * y, max(3, u),
                              f"One pencil costs {u * x}/{x} = Rs. {u}. So {y} pencils cost {u} × {y} = Rs. {u * y}."))
        else:
            a, b = rng.choice([(3, 2), (4, 3), (5, 4), (7, 5), (3, 4)])
            g = b * rng.choice([4, 5, 6, 8])
            out.append(_num_q(rng, t, f"The ratio of boys to girls in a class is {a}:{b}. If there are {g} girls, how many boys are there?", g * a // b, 2,
                              f"Boys = girls × {a}/{b} = {g} × {a}/{b} = {g * a // b}."))
    return out


def gen_averages(rng):
    t, out = "Averages", []
    for i in range(PER_TOPIC):
        kind = i % 4
        if kind == 0:
            n, avg = rng.choice([4, 5, 6]), rng.randint(12, 40)
            nums = [rng.randint(avg - 8, avg + 8) for _ in range(n - 1)]
            nums.append(n * avg - sum(nums))
            out.append(_num_q(rng, t, f"What is the average of these numbers: {', '.join(map(str, nums))}?", avg, 2,
                              f"Sum = {sum(nums)} and there are {n} numbers, so average = {sum(nums)}/{n} = {avg}."))
        elif kind == 1:
            n, a, k = rng.choice([9, 14, 19, 24]), rng.choice([14, 15, 16, 18]), rng.choice([1, 2])
            teacher = (n + 1) * (a + k) - n * a
            out.append(_num_q(rng, t, f"The average age of {n} students is {a} years. When their teacher's age is included, the average becomes {a + k} years. What is the teacher's age?",
                              teacher, 3, f"Total with teacher = {n + 1} × {a + k} = {(n + 1) * (a + k)}. Students' total = {n} × {a} = {n * a}. Teacher = {teacher}."))
        elif kind == 2:
            a, b = rng.choice([(20, 16), (30, 26), (24, 20), (18, 14)])
            last2 = (5 * a - 3 * b) // 2
            out.append(_num_q(rng, t, f"The average of 5 numbers is {a} and the average of the first 3 of them is {b}. What is the average of the other 2?", last2, 2,
                              f"Total of 5 = {5 * a}. Total of first 3 = {3 * b}. Remaining 2 sum to {5 * a - 3 * b}, so their average is {last2}."))
        else:
            n = rng.choice([9, 11, 15, 21, 51, 99])
            out.append(_num_q(rng, t, f"What is the average of the first {n} natural numbers?", (n + 1) // 2, 2,
                              f"Average of 1 to n = (n + 1)/2 = ({n} + 1)/2 = {(n + 1) // 2}."))
    return out


def gen_number_systems(rng):
    t, out = "Number Systems", []
    for i in range(PER_TOPIC):
        kind = i % 5
        if kind == 0:
            g, m, n = rng.choice([2, 3, 4, 5, 6, 7, 8, 9]), *rng.choice([(2, 3), (3, 4), (2, 5), (3, 5), (4, 5), (5, 7)])
            a, b = g * m, g * n
            out.append(_num_q(rng, t, f"What is the HCF of {a} and {b}?", g, 1, f"{a} = {g} × {m} and {b} = {g} × {n}, and {m}, {n} share no factor, so HCF = {g}."))
        elif kind == 1:
            a, b = rng.choice([(4, 6), (6, 8), (8, 12), (9, 12), (10, 15), (12, 18), (14, 21), (15, 20)])
            l = a * b // math.gcd(a, b)
            out.append(_num_q(rng, t, f"What is the LCM of {a} and {b}?", l, 6, f"LCM = (a × b)/HCF = {a} × {b}/{math.gcd(a, b)} = {l}."))
        elif kind == 2:
            a, b = rng.randint(100, 999), rng.choice([7, 8, 9, 11, 12, 13])
            out.append(_num_q(rng, t, f"What is the remainder when {a} is divided by {b}?", a % b, 1, f"{a} = {b} × {a // b} + {a % b}, so the remainder is {a % b}.", ok=lambda v: 0 <= v < b))
        elif kind == 3:
            n = rng.choice([10, 20, 25, 30, 40, 50, 100])
            out.append(_num_q(rng, t, f"What is the sum of all natural numbers from 1 to {n}?", n * (n + 1) // 2, max(5, n), f"Sum = n(n+1)/2 = {n} × {n + 1}/2 = {n * (n + 1) // 2}."))
        else:
            n = rng.choice([10, 20, 30, 50])
            primes = sum(1 for k in range(2, n + 1) if all(k % d for d in range(2, int(k ** 0.5) + 1)))
            out.append(_num_q(rng, t, f"How many prime numbers are there from 1 to {n}?", primes, 1, f"Counting the primes up to {n} gives {primes}."))
    return out


def gen_probability(rng):
    t, out = "Probability", []
    for i in range(PER_TOPIC):
        kind = i % 5
        if kind == 0:
            s = rng.choice([2, 3, 4, 5, 6, 8, 9, 10, 11, 12])
            ways = sum(1 for a in range(1, 7) for b in range(1, 7) if a + b == s)
            out.append(_frac_q(rng, t, f"Two fair dice are rolled together. What is the probability that the sum is {s}?", Fraction(ways, 36),
                               f"There are 36 equally likely outcomes and {ways} give a sum of {s}, so P = {ways}/36 = {_frac(Fraction(ways, 36))}."))
        elif kind == 1:
            name, count = rng.choice([("a king", 4), ("a heart", 13), ("a red card", 26), ("a face card (J, Q, K)", 12), ("the queen of spades", 1), ("an ace", 4)])
            out.append(_frac_q(rng, t, f"One card is drawn at random from a standard pack of 52 cards. What is the probability that it is {name}?", Fraction(count, 52),
                               f"{count} favourable cards out of 52, so P = {count}/52 = {_frac(Fraction(count, 52))}."))
        elif kind == 2:
            n = rng.choice([2, 3, 4])
            k = rng.randint(1, n - 1) if n > 2 else 1
            c = Fraction(math.comb(n, k), 2 ** n)
            out.append(_frac_q(rng, t, f"A fair coin is tossed {n} times. What is the probability of getting exactly {k} head{'s' if k > 1 else ''}?", c,
                               f"Favourable outcomes = C({n},{k}) = {math.comb(n, k)} out of 2^{n} = {2 ** n}, so P = {_frac(c)}."))
        elif kind == 3:
            r, b = rng.choice([(3, 5), (4, 6), (2, 8), (5, 3), (6, 4), (7, 3)])
            out.append(_frac_q(rng, t, f"A bag holds {r} red and {b} blue balls. One ball is picked at random. What is the probability that it is red?", Fraction(r, r + b),
                               f"P(red) = {r}/({r}+{b}) = {_frac(Fraction(r, r + b))}."))
        else:
            k = rng.choice([1, 2, 3, 4])
            out.append(_frac_q(rng, t, f"A fair die is rolled once. What is the probability of getting a number greater than {k}?", Fraction(6 - k, 6),
                               f"Numbers greater than {k}: {6 - k} of 6 outcomes, so P = {_frac(Fraction(6 - k, 6))}."))
    return out


def gen_pnc(rng):
    t, out = "Permutations and Combinations", []
    for i in range(PER_TOPIC):
        kind = i % 5
        if kind == 0:
            n, r = rng.choice([(5, 2), (6, 3), (7, 2), (8, 3), (6, 2)])
            out.append(_num_q(rng, t, f"In how many ways can {r} people be seated in a row from a group of {n} people?", math.perm(n, r), max(3, math.perm(n, r) // 8),
                              f"Arrangements = P({n},{r}) = {n}!/({n}-{r})! = {math.perm(n, r)}."))
        elif kind == 1:
            n, r = rng.choice([(6, 2), (7, 3), (8, 2), (10, 3), (9, 4)])
            out.append(_num_q(rng, t, f"In how many ways can a committee of {r} be chosen from {n} people?", math.comb(n, r), max(3, math.comb(n, r) // 8),
                              f"Selections = C({n},{r}) = {n}!/({r}!({n}-{r})!) = {math.comb(n, r)}."))
        elif kind == 2:
            w = rng.choice(["GOA", "PUNE", "DELHI", "NAGPUR", "AGRA", "LEVEL", "APPLE", "BANANA"])
            from collections import Counter
            denom = 1
            for c in Counter(w).values():
                denom *= math.factorial(c)
            ans = math.factorial(len(w)) // denom
            out.append(_num_q(rng, t, f"In how many different ways can the letters of the word '{w}' be arranged?", ans, max(2, ans // 8),
                              f"{len(w)} letters give {len(w)}! arrangements; repeated letters are divided out: {len(w)}!/{denom} = {ans}."))
        elif kind == 3:
            n = rng.choice([5, 6, 8, 10, 12])
            out.append(_num_q(rng, t, f"{n} people are at a party and each shakes hands once with every other person. How many handshakes are there?", math.comb(n, 2), 3,
                              f"Each handshake is a pair: C({n},2) = {n} × {n - 1}/2 = {math.comb(n, 2)}."))
        else:
            k, L = rng.choice([(5, 3), (6, 3), (5, 2), (7, 2)])
            out.append(_num_q(rng, t, f"How many {L}-digit numbers can be formed from the digits 1 to {k} if no digit is repeated?", math.perm(k, L), 4,
                              f"Choose and arrange {L} of {k} digits: P({k},{L}) = {math.perm(k, L)}."))
    return out


def gen_number_series(rng):
    t, out = "Number Series", []
    for i in range(PER_TOPIC):
        kind = i % 6
        if kind == 0:
            a, d = rng.randint(2, 20), rng.randint(2, 9)
            terms = [a + d * k for k in range(4)]
            ans, rule = a + 4 * d, f"adds {d} each time"
        elif kind == 1:
            a, r = rng.choice([2, 3, 4, 5]), rng.choice([2, 3])
            terms = [a * r ** k for k in range(4)]
            ans, rule = a * r ** 4, f"multiplies by {r} each time"
        elif kind == 2:
            k0 = rng.randint(2, 8)
            terms = [(k0 + k) ** 2 for k in range(4)]
            ans, rule = (k0 + 4) ** 2, "lists consecutive square numbers"
        elif kind == 3:
            s, f = rng.randint(1, 9), rng.randint(1, 3)
            terms = [s]
            for k in range(4):
                terms.append(terms[-1] + f + k)
            ans, rule = terms[-1] + f + 4, "adds an amount that grows by 1 each step"
        elif kind == 4:
            x, a, b = rng.randint(5, 20), rng.randint(4, 9), rng.randint(1, 3)
            terms = [x]
            for k in range(4):
                terms.append(terms[-1] + (a if k % 2 == 0 else -b))
            ans, rule = terms[-1] + a, f"alternately adds {a} and subtracts {b}"
        else:
            p, q = rng.randint(1, 4), rng.randint(2, 6)
            terms = [p, q]
            for _ in range(3):
                terms.append(terms[-1] + terms[-2])
            ans, rule = terms[-1] + terms[-2], "makes each term the sum of the two before it"
        out.append(_num_q(rng, t, f"Find the next number in the series: {', '.join(map(str, terms))}, ?", ans, max(2, abs(ans) // 10),
                          f"The series {rule}, so the next number is {ans}."))
    return out


def _shift(word, k):
    return "".join(chr((ord(c) - 65 + k) % 26 + 65) for c in word)


def gen_coding(rng):
    t, out = "Coding and Decoding", []
    words = ["CAT", "DOG", "SUN", "MOON", "STAR", "BOOK", "TREE", "FISH", "LAMP", "RAIN"]
    for i in range(PER_TOPIC):
        w = words[i % len(words)]
        kind = i % 4
        if kind == 0:
            k = rng.randint(1, 4)
            ans = _shift(w, k)
            wrongs = [_shift(w, k + 1), _shift(w, k - 1), _shift(w, k + 2)]
            stem = f"In a certain code every letter is replaced by the letter {k} place{'s' if k > 1 else ''} ahead of it in the alphabet (A becomes {_shift('A', k)}). How is '{w}' written in this code?"
            expl = f"Move each letter {k} step{'s' if k > 1 else ''} forward: {w} → {ans}."
        elif kind == 1:
            ans = "".join(chr(155 - ord(c)) for c in w)
            wrongs = [_shift(w, 1), w[::-1], _shift(w, 3)]
            stem = f"If A is coded as Z, B as Y, C as X and so on (reverse alphabet), how is '{w}' coded?"
            expl = f"Each letter is replaced by its mirror letter (A↔Z, B↔Y ...): {w} → {ans}."
        elif kind == 2:
            ans = str(sum(ord(c) - 64 for c in w))
            vals = int(ans)
            wrongs = [str(vals + 1), str(vals - 2), str(vals + 3)]
            stem = f"If A = 1, B = 2, C = 3 ... Z = 26, what is the sum of the letter values of '{w}'?"
            expl = "Add the position of each letter: " + " + ".join(str(ord(c) - 64) for c in w) + f" = {ans}."
        else:
            k = rng.randint(1, 3)
            ex, tgt = "CAT", w
            ans = _shift(tgt, k)
            wrongs = [_shift(tgt, k + 1), _shift(tgt, -k), _shift(tgt, k + 2)]
            stem = f"In a certain code, 'CAT' is written as '{_shift(ex, k)}'. How is '{tgt}' written in the same code?"
            expl = f"CAT → {_shift(ex, k)} shifts every letter {k} place(s) forward. Applying the same rule: {tgt} → {ans}."
        wrongs = [x for x in dict.fromkeys(wrongs) if x != ans][:3]
        opts, idx = _shuffled(rng, ans, wrongs)
        out.append({"topic": t, "stem": stem, "options": opts, "correct": idx, "explanation": expl})
    return out


def gen_directions(rng):
    t, out = "Directions", []
    names = ["North", "East", "South", "West"]
    triples = [(3, 4, 5), (6, 8, 10), (5, 12, 13), (9, 12, 15), (8, 15, 17), (12, 16, 20)]
    for i in range(8):
        if i % 2 == 0:
            a, b, c = triples[(i // 2) % len(triples)]
            x = rng.choice([2, 3, 4, 5])
            out.append(_num_q(rng, t, f"A man walks {a + x} km north, then {b} km east, then {x} km south. How far is he from his starting point (in km)?", c, 1,
                              f"Net north = {a + x} − {x} = {a} km and east = {b} km. Distance = √({a}² + {b}²) = {c} km."))
        else:
            start = rng.randrange(4)
            turns = [rng.choice([("right", 1), ("left", -1), ("around", 2)]) for _ in range(3)]
            end = (start + sum(d for _, d in turns)) % 4
            phrase = ", then ".join("turns " + ("around (180°)" if n == "around" else n) for n, _ in turns)
            out.append({"topic": t, "stem": f"A person is facing {names[start]}. He {phrase}. Which direction is he facing now?", "options": names,
                        "correct": end, "explanation": f"Right = +90°, left = −90°, around = 180°. Starting from {names[start]}, the turns end facing {names[end]}."})
    return out


GENERATORS = [("quant", gen_percentages, 11), ("quant", gen_profit_loss, 12), ("quant", gen_interest, 13), ("quant", gen_time_work, 14),
              ("quant", gen_speed, 15), ("quant", gen_ratio, 16), ("quant", gen_averages, 17), ("quant", gen_number_systems, 18),
              ("quant", gen_probability, 19), ("quant", gen_pnc, 20), ("logical", gen_number_series, 21), ("logical", gen_coding, 22),
              ("logical", gen_directions, 23)]


def generated_questions():
    """[(key, section, question_dict)] with fixed seeds, so the bank is stable."""
    result = []
    for section, gen, seed in GENERATORS:
        for attempt in range(200):          # retry with a new fixed seed until no question repeats
            questions = gen(random.Random(seed + 1000 * attempt))
            if len({q["stem"] for q in questions}) == len(questions):
                break
        else:                               # pragma: no cover - would mean a generator has too few variations
            raise RuntimeError(f"{gen.__name__} cannot produce unique questions")
        for n, q in enumerate(questions, start=1):
            slug = q["topic"].lower().replace(" ", "-").replace(",", "")
            result.append((f"{section}-{slug}-{n:02d}", section, q))
    return result
