from langchain_core.tools import tool


@tool
def get_tax_rate(income: float) -> dict:
    """소득금액에 따른 소득세 세율 및 누진공제액을 반환합니다.

    Args:
        income: 과세표준 금액 (원)

    Returns:
        세율, 누진공제액, 산출세액 정보
    """
    brackets = [
        (14_000_000,  0.06,         0),
        (50_000_000,  0.15,   1_260_000),
        (88_000_000,  0.24,   5_760_000),
        (150_000_000, 0.35,  15_440_000),
        (300_000_000, 0.38,  19_940_000),
        (500_000_000, 0.40,  25_940_000),
        (1_000_000_000, 0.42, 35_940_000),
        (float("inf"), 0.45, 65_940_000),
    ]

    for limit, rate, deduction in brackets:
        if income <= limit:
            tax = income * rate - deduction
            return {
                "과세표준": f"{income:,.0f}원",
                "세율": f"{rate * 100:.0f}%",
                "누진공제": f"{deduction:,.0f}원",
                "산출세액": f"{tax:,.0f}원",
            }

    return {"error": "계산 오류"}


@tool
def get_vat_calculation(supply_amount: float, is_inclusive: bool = False) -> dict:
    """부가가치세를 계산합니다.

    Args:
        supply_amount: 공급가액 또는 공급대가
        is_inclusive: True면 부가세 포함 금액(공급대가), False면 공급가액

    Returns:
        공급가액, 부가세액, 공급대가 정보
    """
    if is_inclusive:
        supply = supply_amount / 1.1
        vat = supply_amount - supply
    else:
        supply = supply_amount
        vat = supply_amount * 0.1

    total = supply + vat

    return {
        "공급가액": f"{supply:,.0f}원",
        "부가가치세": f"{vat:,.0f}원",
        "공급대가(합계)": f"{total:,.0f}원",
        "세율": "10%",
    }


@tool
def get_depreciation(
    cost: float,
    salvage: float,
    useful_life: int,
    method: str = "straight_line",
    year: int = 1,
    rate: float = None,
) -> dict:
    """유형자산 감가상각비를 계산합니다.

    Args:
        cost: 취득원가
        salvage: 잔존가치
        useful_life: 내용연수
        method: 'straight_line'(정액법) 또는 'declining_balance'(정률법)
        year: 몇 년차 상각인지 (정률법에서 사용)
        rate: 정률법 상각률 (미입력 시 자동 계산 불가, 직접 입력 필요)

    Returns:
        감가상각비, 누계 감가상각비, 장부금액 정보
    """
    if method == "straight_line":
        annual_dep = (cost - salvage) / useful_life
        accumulated = annual_dep * year
        book_value = cost - accumulated
        return {
            "방법": "정액법",
            "취득원가": f"{cost:,.0f}원",
            "잔존가치": f"{salvage:,.0f}원",
            "내용연수": f"{useful_life}년",
            "연간 감가상각비": f"{annual_dep:,.0f}원",
            f"{year}년차 누계상각": f"{accumulated:,.0f}원",
            "장부금액": f"{book_value:,.0f}원",
        }
    elif method == "declining_balance":
        if rate is None:
            return {"error": "정률법 사용 시 상각률(rate)을 입력해주세요."}
        book_value = cost
        accumulated = 0
        for y in range(1, year + 1):
            dep = book_value * rate
            accumulated += dep
            book_value -= dep
        return {
            "방법": "정률법",
            "취득원가": f"{cost:,.0f}원",
            "상각률": f"{rate * 100:.1f}%",
            f"{year}년차 감가상각비": f"{dep:,.0f}원",
            f"{year}년차 누계상각": f"{accumulated:,.0f}원",
            "장부금액": f"{book_value:,.0f}원",
        }
    else:
        return {"error": "method는 'straight_line' 또는 'declining_balance'여야 합니다."}


@tool
def get_manufacturing_cost(
    beginning_wip: float,
    direct_material: float,
    direct_labor: float,
    overhead: float,
    ending_wip: float,
) -> dict:
    """제조원가명세서를 계산합니다.

    Args:
        beginning_wip: 기초재공품
        direct_material: 직접재료비
        direct_labor: 직접노무비
        overhead: 제조간접비
        ending_wip: 기말재공품

    Returns:
        당기총제조원가, 당기제품제조원가 등
    """
    total_current = direct_material + direct_labor + overhead
    cost_of_goods_manufactured = beginning_wip + total_current - ending_wip

    return {
        "기초재공품": f"{beginning_wip:,.0f}원",
        "직접재료비": f"{direct_material:,.0f}원",
        "직접노무비": f"{direct_labor:,.0f}원",
        "제조간접비": f"{overhead:,.0f}원",
        "당기총제조원가": f"{total_current:,.0f}원",
        "기말재공품": f"{ending_wip:,.0f}원",
        "당기제품제조원가": f"{cost_of_goods_manufactured:,.0f}원",
    }


SHARED_TOOLS = [
    get_tax_rate,
    get_vat_calculation,
    get_depreciation,
    get_manufacturing_cost,
]
