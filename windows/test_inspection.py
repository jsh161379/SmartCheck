
# test_inspection.py

from inspection import inspect_items


def run_test(name, selected, frames, expected):
    result = inspect_items(selected, frames)

    actual = result["result"]
    success = actual == expected

    print(f"\n[{name}]")
    print(f"예상 결과: {expected}")
    print(f"실제 결과: {actual}")
    print(f"탐지 횟수: {result['counts']}")
    print(f"누락 물품: {result['missing_items']}")
    print(f"불확실 물품: {result['uncertain_items']}")
    print("테스트:", "성공" if success else "실패")

    assert success, f"{name}: 예상 {expected}, 실제 {actual}"


def main():
    # 1. 모든 물품 정상 탐지
    run_test(
        "PASS 테스트",
        ["book", "cell phone", "scissors"],
        [
            {"book", "cell phone", "scissors"},
            {"book", "cell phone", "scissors"},
            {"book", "cell phone", "scissors"},
            {"book", "cell phone", "scissors"},
            {"book", "scissors"}
        ],
        "PASS"
    )

    # 2. 휴대폰 누락
    run_test(
        "FAIL 테스트",
        ["book", "cell phone", "scissors"],
        [
            {"book", "scissors"},
            {"book", "scissors"},
            {"book", "scissors"},
            {"book", "scissors"},
            {"book", "scissors"}
        ],
        "FAIL"
    )

    # 3. 휴대폰 탐지 불안정
    run_test(
        "RECHECK 테스트",
        ["book", "cell phone", "scissors"],
        [
            {"book", "cell phone", "scissors"},
            {"book", "scissors"},
            {"book", "cell phone", "scissors"},
            {"book", "scissors"},
            {"book", "scissors"}
        ],
        "RECHECK"
    )

    # 4. 선택하지 않은 물품 제외
    run_test(
        "선택 물품만 검사",
        ["book"],
        [
            {"book"},
            {"book"},
            {"book"},
            {"book"},
            {"book"}
        ],
        "PASS"
    )

    # 5. 누락과 불확실이 동시에 발생
    run_test(
        "FAIL 우선순위 테스트",
        ["book", "cell phone", "scissors"],
        [
            {"book", "cell phone"},
            {"book"},
            {"book", "cell phone"},
            {"book"},
            {"book"}
        ],
        "FAIL"
    )

    # 6. 검사 대상 미선택
    try:
        inspect_items([], [set() for _ in range(5)])
        raise AssertionError("미선택 검사에서 오류가 발생해야 합니다.")
    except ValueError:
        print("\n[검사 대상 미선택] 테스트: 성공")

    print("\n=== 모든 테스트 통과 ===")


if __name__ == "__main__":
    main()
