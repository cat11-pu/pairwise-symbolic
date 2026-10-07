"""符号表达式化简内核（纯标准库，行为完全确定）。

表达式一律写成元组：("num", 3) 是整数常量；("sym", "x") 是小写名字，可交换；
("nc", "A") 是大写名字，非交换的原子（例如矩阵）；("add", (a, b, ...)) 与
("mul", (a, b, ...)) 是两项以上的和与积；("pow", base, k) 是底数的 k 次幂。

parse(text) 读表达式，simplify() 化简成规范形式，to_text() 渲染回文本。规范形式
见 README：括号摊平、常量折叠、同类项系数相加、同底数幂合并、零与一消除、加项按
次数从高到低、乘积里整系数在最前、任何因子不得跨过非交换原子。
"""

LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
DIGITS = "0123456789"
KINDS = ("num", "sym", "nc", "add", "mul", "pow")


class SymbolicError(Exception):
    """文本写错、节点形状不对或指数不合法。"""


def parse(text):
    """把一段文本读成表达式，原样保留括号与写法。"""
    if not isinstance(text, str):
        raise TypeError("表达式必须是字符串")
    position = [0]
    node = _read_sum(text, position)
    _skip_space(text, position)
    if position[0] < len(text):
        raise SymbolicError("位置 %d 的字符 %r 不属于表达式" % (position[0], text[position[0]]))
    return node


def _skip_space(text, position):
    """把位置移过空白。"""
    while position[0] < len(text) and text[position[0]].isspace():
        position[0] += 1


def _read_sum(text, position):
    """读一个和式：最松的一层，每一项都可以带正负号。"""
    terms = []
    while True:
        _skip_space(text, position)
        negative = False
        while position[0] < len(text) and text[position[0]] in "+-":
            negative = negative != (text[position[0]] == "-")
            position[0] += 1
            _skip_space(text, position)
        term = _read_product(text, position)
        terms.append(_negated(term) if negative else term)
        _skip_space(text, position)
        if position[0] >= len(text) or text[position[0]] not in "+-":
            break
    return _packed("add", terms)


def _read_product(text, position):
    """读一个乘积。"""
    factors = []
    while True:
        factors.append(_read_power(text, position))
        _skip_space(text, position)
        if position[0] >= len(text) or text[position[0]] != "*":
            break
        position[0] += 1
    return _packed("mul", factors)


def _read_power(text, position):
    """读一个原子，后面可以跟一个非负整数指数。"""
    base = _read_atom(text, position)
    _skip_space(text, position)
    if position[0] >= len(text) or text[position[0]] != "^":
        return base
    position[0] += 1
    _skip_space(text, position)
    start = position[0]
    while position[0] < len(text) and text[position[0]] in DIGITS:
        position[0] += 1
    if start == position[0]:
        raise SymbolicError("^ 在位置 %d 后面要跟一个非负整数指数" % (start,))
    return ("pow", base, int(text[start:position[0]]))


def _read_atom(text, position):
    """读一个数字、一个名字或一对括号。"""
    _skip_space(text, position)
    if position[0] >= len(text):
        raise SymbolicError("表达式在还需要一个值的地方结束")
    char = text[position[0]]
    if char == "(":
        opened = position[0]
        position[0] += 1
        node = _read_sum(text, position)
        _skip_space(text, position)
        if position[0] >= len(text) or text[position[0]] != ")":
            raise SymbolicError("位置 %d 的左括号没有闭合" % (opened,))
        position[0] += 1
        return node
    if char in DIGITS:
        start = position[0]
        while position[0] < len(text) and text[position[0]] in DIGITS:
            position[0] += 1
        return ("num", int(text[start:position[0]]))
    if char in LETTERS:
        position[0] += 1
        return ("nc", char) if char.isupper() else ("sym", char)
    raise SymbolicError("位置 %d 的字符 %r 不属于表达式" % (position[0], char))


def _negated(node):
    """把一个节点取反。"""
    return ("mul", (("num", -1), node))


def _packed(kind, items):
    """把 children 装成节点；只有一个 child 时就是它自己。"""
    return items[0] if len(items) == 1 else (kind, tuple(items))


def _flatten(kind, children):
    """把同类 children 里嵌着的同类节点摊平。"""
    flat = []
    for child in children:
        flat.extend(child[1] if child[0] == kind else (child,))
    return flat


def to_text(node):
    """把一个表达式节点渲染成文本。"""
    kind = _shape(node)
    if kind == "num":
        return str(node[1])
    if kind in ("sym", "nc"):
        return node[1]
    if kind == "pow":
        return _wrapped(node[1], ("add", "mul", "pow")) + "^" + str(node[2])
    if kind == "mul":
        factors = [_wrapped(factor, ("add", "mul")) for factor in node[1]]
        if len(factors) > 1 and node[1][0][0] == "num":
            coefficient = node[1][0][1]
            body = "*".join(factors[1:])
            if coefficient == 1:
                return body
            return ("-" + body) if coefficient == -1 else (str(coefficient) + "*" + body)
        return "*".join(factors)
    parts = [to_text(term) for term in node[1]]
    return parts[0] + "".join((" - " + part[1:]) if part.startswith("-")
                              else (" + " + part) for part in parts[1:])


def _wrapped(node, bracketed):
    """渲染一个因子或底数：种类在 bracketed 里就加括号。"""
    text = to_text(node)
    return "(" + text + ")" if node[0] in bracketed else text


def _shape(node):
    """确认一个节点是什么，形状不对就报错。"""
    if not isinstance(node, tuple) or not node or node[0] not in KINDS:
        raise SymbolicError("不是一个表达式节点: %r" % (node,))
    kind = node[0]
    if len(node) != (3 if kind == "pow" else 2) or ((kind in ("add", "mul")) and not node[1]):
        raise SymbolicError("节点 %r 的形状不对" % (node,))
    wanted = int if kind == "num" else str
    if kind in ("num", "sym", "nc") and (isinstance(node[1], bool)
                                         or not isinstance(node[1], wanted)):
        raise SymbolicError("原子 %r 的取值形状不对" % (node,))
    return kind


def simplify(node):
    """把一个表达式化简成规范形式。"""
    kind = _shape(node)
    if kind in ("num", "sym", "nc"):
        return node
    if kind == "pow":
        base = simplify(node[1])
        if isinstance(node[2], bool) or not isinstance(node[2], int):
            raise SymbolicError("幂的指数必须是整数，不是 %r" % (node[2],))
        return _make_power(base, node[2])
    children = _flatten(kind, [simplify(child) for child in node[1]])
    return _make_sum(children) if kind == "add" else _make_product(children)


def _make_sum(terms):
    """和式的规范形式：摊平、折叠常量、合并同类项、按次数排列。"""
    flat = _flatten("add", terms)
    total = 0
    order = []
    coefficients = {}
    for term in flat:
        coefficient, skeleton = _parts(term)
        if skeleton is None:
            total += coefficient
        else:
            if skeleton not in coefficients:
                order.append(skeleton)
            coefficients[skeleton] = coefficients.get(skeleton, 0) + coefficient
    parts = [("num", total)] if total else []
    parts.extend(_scaled(skeleton, coefficients[skeleton])
                 for skeleton in order if coefficients[skeleton])
    if not parts:
        return ("num", 0)
    return parts[0] if len(parts) == 1 else ("add", tuple(sorted(parts, key=_term_key)))


def _parts(term):
    """一个加项的系数与骨架；常量没有骨架。"""
    if term[0] == "num":
        return term[1], None
    if term[0] == "mul" and term[1][0][0] == "num":
        return term[1][0][1], _packed("mul", term[1][1:])
    return 1, term


def _scaled(skeleton, coefficient):
    """把整系数放到骨架前面。"""
    if coefficient == 1:
        return skeleton
    factors = skeleton[1] if skeleton[0] == "mul" else (skeleton,)
    return ("mul", (("num", coefficient),) + factors)


def _term_key(term):
    """加项的排序键：次数高的在前，同次数按文本升序。"""
    text = to_text(term)
    return (-_degree(term), text[1:] if text.startswith("-") else text)


def _degree(node):
    """一个节点算几次：名字的幂次之和，和式取各项里最大的。"""
    if node[0] in ("num", "sym", "nc"):
        return 0 if node[0] == "num" else 1
    if node[0] == "pow":
        return node[2] * _degree(node[1])
    counts = [_degree(child) for child in node[1]]
    return sum(counts) if node[0] == "mul" else max(counts)


def _make_product(factors):
    """积的规范形式：摊平、乘开括号、折叠整系数、合并同底数幂。"""
    flat = _flatten("mul", factors)
    for index, factor in enumerate(flat):
        if factor[0] == "add":
            return _distribute(flat, index)
    coefficient = 1
    units = []
    for factor in flat:
        if factor[0] == "num":
            coefficient *= factor[1]
        else:
            units.append(factor)
    if not units:
        return ("num", coefficient)
    units = _combine_runs(units)
    if coefficient == 0:
        return ("num", 0)
    if coefficient == 1:
        return _packed("mul", units)
    return ("mul", (("num", coefficient),) + tuple(units))


def _distribute(factors, index):
    """把乘积里第 index 个和式乘开，因子的顺序保持不变。"""
    return _make_sum([_make_product(factors[:index] + [term] + factors[index + 1:])
                      for term in factors[index][1]])


def _combine_runs(units):
    """逐段处理因子：只有可交换的那几段才能排序与合并。"""
    result = []
    run = []
    for unit in units:
        if _movable(unit):
            run.append(unit)
            continue
        if run:
            result.extend(_combine_run(run))
            run = []
        _append_unit(result, unit)
    if run:
        result.extend(_combine_run(run))
    return result


def _append_unit(result, unit):
    """把非交换的因子放回原地；相邻的同底数幂合并成一个幂。"""
    base, exponent = _power_parts(unit)
    if result and not _movable(result[-1]):
        last_base, last_exponent = _power_parts(result[-1])
        if last_base == base:
            result[-1] = _make_power(base, last_exponent + exponent)
            return
    result.append(base if exponent == 1 else _make_power(base, exponent))


def _combine_run(run):
    """一段可交换的因子：同底数的指数相加，再按文本升序。"""
    order = []
    exponents = {}
    for factor in run:
        base, exponent = _power_parts(factor)
        if base not in exponents:
            order.append(base)
        exponents[base] = exponents.get(base, 0) + exponent
    return sorted([base if exponents[base] == 1 else _make_power(base, exponents[base])
                   for base in order], key=to_text)


def _power_parts(factor):
    """某一段里一个因子的底数与指数。"""
    if factor[0] == "pow":
        return factor[1], factor[2]
    return factor, 1


def _movable(node):
    """能不能被重新排序：整系数是中心的，小写名字是标量，含非交换原子的一律留下。"""
    if node[0] == "nc":
        return False
    if node[0] in ("num", "sym"):
        return True
    if node[0] == "pow":
        return _movable(node[1])
    return all(_movable(part) for part in node[1])


def _make_power(base, exponent):
    """幂的规范形式：常量折叠、零与一消除、幂套幂与积的幂摊开。"""
    if exponent < 0:
        raise SymbolicError("只支持非负整数指数，不是 %r" % (exponent,))
    if base[0] == "num":
        if base[1] == 0 and exponent == 0:
            raise SymbolicError("0 的 0 次幂没有定义")
        return ("num", base[1] ** exponent)
    if exponent == 0:
        return ("num", 1)
    if exponent == 1:
        return base
    if base[0] == "pow":
        return _make_power(base[1], base[2] * exponent)
    if base[0] == "mul" and _movable(base):
        return _make_product([_make_power(factor, exponent) for factor in base[1]])
    return ("pow", base, exponent)
