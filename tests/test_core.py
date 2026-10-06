"""符号表达式化简内核的验收测试。

在项目根目录执行：

    python3 -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from symbolic import SymbolicError, parse, simplify, to_text


VALUES = {"x": 2, "y": 3, "z": 5, "A": 7, "B": 11}


def canonical(text):
    """化简之后的文本；意外抛出的异常算测试失败。"""
    try:
        return to_text(simplify(parse(text)))
    except Exception as error:
        raise AssertionError("%r 抛出 %s: %s" % (text, type(error).__name__, error))


def error_of(text):
    """这段文本必须抛 SymbolicError，否则算测试失败。"""
    try:
        simplify(parse(text))
    except SymbolicError as error:
        return error
    except Exception as error:
        raise AssertionError("%r 抛出 %s 而不是 SymbolicError: %s"
                             % (text, type(error).__name__, error))
    raise AssertionError("%r 被接受，没有报错" % (text,))


def value_of(node, values):
    """测试自己的求值器，与 symbolic 的化简逻辑无关，用来核对取值。"""
    kind = node[0]
    if kind == "num":
        return node[1]
    if kind in ("sym", "nc"):
        return values[node[1]]
    if kind == "add":
        return sum(value_of(child, values) for child in node[1])
    if kind == "mul":
        total = 1
        for child in node[1]:
            total *= value_of(child, values)
        return total
    return value_of(node[1], values) ** node[2]


def values_of(text):
    """化简前后各求一次值；意外抛出的异常算测试失败。"""
    try:
        expression = parse(text)
        return value_of(expression, VALUES), value_of(simplify(expression), VALUES)
    except Exception as error:
        raise AssertionError("%r 抛出 %s: %s" % (text, type(error).__name__, error))


class ParseTest(unittest.TestCase):
    def test_parse_and_render(self):
        self.assertEqual(to_text(parse("x + y")), "x + y")
        self.assertEqual(to_text(parse("2*x*A")), "2*x*A")
        self.assertEqual(to_text(parse("x - y")), "x - y")
        self.assertEqual(to_text(parse("-(x + 1)")), "-(x + 1)")
        self.assertEqual(to_text(parse("(x + 1)^2")), "(x + 1)^2")
        self.assertEqual(to_text(parse("A^2*B")), "A^2*B")
        self.assertEqual(to_text(parse("  2 * ( x + 3 )  ")), "2*(x + 3)")
        self.assertEqual(value_of(parse("2*x + 1"), {"x": 3}), 7)
        self.assertEqual(value_of(parse("(x + y)*(x - y)"), {"x": 4, "y": 1}), 15)
        with self.assertRaises(TypeError):
            parse(None)


class FoldTest(unittest.TestCase):
    def test_constants_are_folded(self):
        self.assertEqual(canonical("2 + 3"), "5")
        self.assertEqual(canonical("2*3"), "6")
        self.assertEqual(canonical("2*3 + 4"), "10")
        self.assertEqual(canonical("x*2*3"), "6*x")
        self.assertEqual(canonical("1*x"), "x")
        self.assertEqual(canonical("x + 0"), "x")
        self.assertEqual(canonical("0 + 0"), "0")
        self.assertEqual(canonical("2^10"), "1024")
        self.assertEqual(canonical("(2*x)^3"), "8*x^3")
        self.assertEqual(canonical("x*y"), "x*y")


class LikeTermsTest(unittest.TestCase):
    def test_like_terms_add_their_coefficients(self):
        self.assertEqual(canonical("2*x + 3*x"), "5*x")
        self.assertEqual(canonical("x + x"), "2*x")
        self.assertEqual(canonical("5*x - 2*x"), "3*x")
        self.assertEqual(canonical("x - x"), "0")
        self.assertEqual(canonical("x^2 - x^2"), "0")
        self.assertEqual(canonical("3*x^2 + 2*x^2"), "5*x^2")
        self.assertEqual(canonical("x*y + x*y"), "2*x*y")
        self.assertEqual(canonical("2*(x + y) + 3*(x + y)"), "5*x + 5*y")
        self.assertEqual(canonical("x*y + 2*x*y - y*x"), "2*x*y")


class NeutralTest(unittest.TestCase):
    def test_zero_and_one_are_dropped(self):
        self.assertEqual(canonical("0*x"), "0")
        self.assertEqual(canonical("0*(x + 1)"), "0")
        self.assertEqual(canonical("x + 0*y"), "x")
        self.assertEqual(canonical("0*x*y"), "0")
        self.assertEqual(canonical("1*x*y"), "x*y")
        self.assertEqual(canonical("x^0"), "1")
        self.assertEqual(canonical("x^1"), "x")
        self.assertEqual(canonical("x^1*y"), "x*y")
        self.assertEqual(canonical("(x*y)^1"), "x*y")


class PowerTest(unittest.TestCase):
    def test_powers_are_merged(self):
        self.assertEqual(canonical("x*x"), "x^2")
        self.assertEqual(canonical("2*x*x"), "2*x^2")
        self.assertEqual(canonical("x*x^2"), "x^3")
        self.assertEqual(canonical("x^2*x^3"), "x^5")
        self.assertEqual(canonical("x^2*y^3*x"), "x^3*y^3")
        self.assertEqual(canonical("(x^2)^3"), "x^6")
        self.assertEqual(canonical("(x^2)^3*x"), "x^7")
        self.assertEqual(canonical("(x*y)^2"), "x^2*y^2")
        self.assertEqual(canonical("A^2*A^3"), "A^5")


class ExpandTest(unittest.TestCase):
    def test_brackets_are_multiplied_out(self):
        self.assertEqual(canonical("2*(x + 3)"), "2*x + 6")
        self.assertEqual(canonical("(x + 3)*2"), "2*x + 6")
        self.assertEqual(canonical("(x + y)*2"), "2*x + 2*y")
        self.assertEqual(canonical("(x + 1)*(y + 2)"), "x*y + 2*x + y + 2")
        self.assertEqual(canonical("x*(y + z) + x*y"), "2*x*y + x*z")
        self.assertEqual(canonical("(x + 1)^2"), "(x + 1)^2")
        self.assertEqual(canonical("A*(x + y)"), "A*x + A*y")


class OrderTest(unittest.TestCase):
    def test_the_canonical_order_is_fixed(self):
        self.assertEqual(canonical("x + y"), canonical("y + x"))
        self.assertEqual(canonical("2*x*y"), canonical("y*2*x"))
        self.assertEqual(canonical("x^2 + 2*x + 1"), canonical("1 + 2*x + x^2"))
        self.assertEqual(canonical("x*y"), canonical("y*x"))
        self.assertEqual(canonical("2 + x"), "x + 2")
        self.assertEqual(canonical("1 + x"), "x + 1")
        self.assertEqual(canonical("x*y + x + 2"), "x*y + x + 2")
        self.assertEqual(canonical("x^2 + 2*x + 1"), "x^2 + 2*x + 1")
        self.assertEqual(canonical("x^1"), canonical("x"))
        self.assertNotEqual(canonical("x"), canonical("x + 1"))


class NonCommutativeTest(unittest.TestCase):
    def test_non_commutative_atoms_keep_their_place(self):
        self.assertEqual(canonical("x*A*y"), "x*A*y")
        self.assertEqual(canonical("y*A*x"), "y*A*x")
        self.assertEqual(canonical("A*x*B"), "A*x*B")
        self.assertEqual(canonical("2*x*A*3*y"), "6*x*A*y")
        self.assertEqual(canonical("(A*B)^2"), "(A*B)^2")
        self.assertEqual(canonical("A*(x + y)"), "A*x + A*y")
        self.assertNotEqual(canonical("x*A*y"), canonical("y*A*x"))


class ValueTest(unittest.TestCase):
    def test_simplification_keeps_the_value(self):
        texts = ("2*x + 3*x", "x - x", "0*y + 5", "2*(x + 3)", "(x + 1)*(y + 2)",
                 "x*x + x", "(2*x + 1)*(x + 3)", "x^2*y + x*y^2", "A*B*A", "2*x*A*y + 0")
        for text in texts:
            before, after = values_of(text)
            self.assertEqual(after, before, "%r 化简前后取值不同：%r -> %r"
                             % (text, before, after))


class ErrorTest(unittest.TestCase):
    def test_malformed_input_is_reported(self):
        for text in ("", "x +", "(x + 1", "x*y)", "2 3", "x^y", "x^-1", "x @ y", "2^", "x*"):
            error_of(text)
        error_of("0^0")
        self.assertRaises(SymbolicError, simplify, "x")
        self.assertRaises(SymbolicError, simplify, ("bogus", 1))
        self.assertRaises(SymbolicError, simplify, ("num", 1.5))
        self.assertRaises(SymbolicError, simplify, ("sym", 7))
        self.assertRaises(SymbolicError, simplify, ("mul", ()))
        self.assertRaises(SymbolicError, simplify, ("pow", ("sym", "x")))
        self.assertRaises(TypeError, parse, None)


if __name__ == "__main__":
    unittest.main()
