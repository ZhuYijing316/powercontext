"""Fault injection: prove the acceptance checker is not a rubber stamp.

A checker that always says PASS proves nothing.  This script deliberately
breaks the submission in six ways and asserts that the matching acceptance
item turns FAIL, then restores the submission and asserts the item is green
again.

Every fault is undone in a ``finally`` block, so the run is safe even when
an assertion fails half way through.

Run it from the ``minimax`` directory::

    python -m validation.fault_injection

The result is written to ``minimax/evidence/fault-injection.md``.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sddctx.config import (  # noqa: E402
    EVIDENCE_DIR,
    REPO_ROOT,
    load_config,
)
from sddctx.evidence import EvidenceRecorder  # noqa: E402
from sddctx.runner import import_material, revert_to_before_snapshot  # noqa: E402
from validation import check_acceptance as ca  # noqa: E402

CONFIG = load_config()
PROJECT = CONFIG.sample_project
SPEC_FILE = REPO_ROOT / "minimax" / "specs" / "jmespath-matches.md"
TARGET_TEST = PROJECT / "tests" / "test_matches.py"
RAW_EVIDENCE = EVIDENCE_DIR / "raw"
PATCH_DIR = EVIDENCE_DIR / "patches"


@dataclass
class Fault:
    """One deliberate break of the submission."""

    fault_id: str
    title: str
    what: str
    expect_fail: list[str]
    inject: Callable[[], None]
    restore: Callable[[], None]
    notes: str = ""
    #: the fault changes the environment, so the config must be rebuilt
    rebuild_config: bool = False


def _run_check(name: str, config: Any = None) -> Any:
    """Run one acceptance check by name and return the Check object."""
    mapping = {
        "runnable": ca.check_runnable,
        "minimax-involved": ca.check_minimax_involved,
        "context-correct": ca.check_context,
        "context-follows-spec-edit": ca.check_spec_follows_edit,
        "database-involved": ca.check_database,
        "state-reuse": ca.check_state_reuse,
        "code-change-effective": ca.check_code_change,
    }
    return mapping[name](config or CONFIG)


def _latest_patch() -> Path:
    patches = sorted(PATCH_DIR.glob("*.patch"))
    if not patches:
        raise SystemExit("no patch file found; run validation.reproduce_evidence first")
    return patches[-1]


def _apply_latest_patch() -> None:
    patch = _latest_patch()
    process = os.system(f'git -C "{REPO_ROOT}" apply --whitespace=nowarn --recount "{patch}"')
    if process != 0:
        raise SystemExit(f"could not re-apply {patch.name}")


# ----------------------------------------------------------------------
# the faults
# ----------------------------------------------------------------------
def fault_spec_rows_deleted() -> Fault:
    store = ca.SeekDBStore(CONFIG.seekdb)
    before = store.counts()

    def inject() -> None:
        with store.connect() as conn:
            store.execute(conn, "DELETE FROM sdd_spec")

    def restore() -> None:
        import_material(CONFIG, EvidenceRecorder("fault-injection-restore"))

    return Fault(
        fault_id="spec-rows-deleted",
        title="seekdb 里的规格行被删掉",
        what="规格条目不在数据库里了，但文件还在 —— 数据库没有真正承担存储职责。",
        expect_fail=["database-involved", "context-correct"],
        inject=inject,
        restore=restore,
        notes=f"删除前 sdd_spec 有 {before.get('specs')} 行",
    )


def fault_implementation_reverted() -> Fault:
    def inject() -> None:
        revert_to_before_snapshot(CONFIG, EvidenceRecorder("fault-injection-revert"))

    def restore() -> None:
        _apply_latest_patch()
        import_material(CONFIG, EvidenceRecorder("fault-injection-restore"))

    return Fault(
        fault_id="implementation-reverted",
        title="实现被撤回到修改前快照",
        what="matches() 没有实现，目标测试因此失败 —— 证明『修改后全绿』不是白送。",
        expect_fail=["code-change-effective"],
        inject=inject,
        restore=restore,
    )


def fault_spec_edited_not_reimported() -> Fault:
    original = SPEC_FILE.read_text(encoding="utf-8")
    marker = "\n<!-- FAULT-INJECTION: 规格被改过但没有重新导入 -->\n"

    def inject() -> None:
        SPEC_FILE.write_text(marker + original, encoding="utf-8")

    def restore() -> None:
        SPEC_FILE.write_text(original, encoding="utf-8")
        import_material(CONFIG, EvidenceRecorder("fault-injection-restore"))

    return Fault(
        fault_id="spec-edited-not-reimported",
        title="规格文件被改了但没有重新导入",
        what="文件与索引里的内容对不上 —— 检索结果指向的已经不是磁盘上的真实内容。",
        expect_fail=["context-correct"],
        inject=inject,
        restore=restore,
    )


def fault_target_test_removed() -> Fault:
    parked = TARGET_TEST.with_suffix(".py.fault-injection")

    def inject() -> None:
        shutil.move(str(TARGET_TEST), str(parked))

    def restore() -> None:
        if parked.exists():
            shutil.move(str(parked), str(TARGET_TEST))

    return Fault(
        fault_id="target-test-removed",
        title="目标测试文件被移走",
        what="测试文件不在了 —— 『修改前失败 / 修改后通过』这条链就没有证据了。",
        expect_fail=["code-change-effective", "context-correct"],
        inject=inject,
        restore=restore,
    )


def fault_powercontext_unreachable() -> Fault:
    original = os.environ.get("POWERCONTEXT_URL", "")

    def inject() -> None:
        os.environ["POWERCONTEXT_URL"] = "http://127.0.0.1:29998"

    def restore() -> None:
        if original:
            os.environ["POWERCONTEXT_URL"] = original
        else:
            os.environ.pop("POWERCONTEXT_URL", None)

    return Fault(
        fault_id="powercontext-unreachable",
        title="PowerContext 不可达，任务状态读不到",
        what="状态存不进去也读不回来 —— 『状态能够复用』这条就不成立。",
        expect_fail=["state-reuse"],
        inject=inject,
        restore=restore,
        rebuild_config=True,
    )


def fault_minimax_records_moved() -> Fault:
    parked = EVIDENCE_DIR / "raw.fault-injection"

    def inject() -> None:
        if parked.exists():
            shutil.rmtree(parked)
        shutil.move(str(RAW_EVIDENCE), str(parked))

    def restore() -> None:
        if parked.exists():
            shutil.move(str(parked), str(RAW_EVIDENCE))

    return Fault(
        fault_id="minimax-records-moved",
        title="MiniMax 的原始调用记录被移走",
        what="拿不出模型的开发记录 —— 『MiniMax 实际参与』无法被核对。",
        expect_fail=["minimax-involved"],
        inject=inject,
        restore=restore,
    )


FAULTS = [
    fault_spec_rows_deleted(),
    fault_implementation_reverted(),
    fault_spec_edited_not_reimported(),
    fault_target_test_removed(),
    fault_powercontext_unreachable(),
    fault_minimax_records_moved(),
]


def main() -> int:
    print("=" * 78)
    print("Fault injection - proving the acceptance checker has teeth")
    print("=" * 78)

    results: list[dict[str, Any]] = []
    all_good = True

    for fault in FAULTS:
        print(f"\n--- {fault.fault_id}: {fault.title}")
        print(f"    {fault.what}")
        try:
            fault.inject()
            observed_fail: list[str] = []
            observed_pass: list[str] = []
            active_config = load_config() if fault.rebuild_config else CONFIG
            for name in fault.expect_fail:
                check = _run_check(name, active_config)
                status = "FAIL" if not check.passed else "PASS"
                print(f"    [{status}] {name}: {check.detail[:110]}")
                if not check.passed:
                    observed_fail.append(name)
                else:
                    observed_pass.append(name)
        finally:
            fault.restore()

        # after the restore the same checks must be green again
        after: list[str] = []
        restore_config = load_config() if fault.rebuild_config else CONFIG
        for name in fault.expect_fail:
            check = _run_check(name, restore_config)
            after.append(f"{name}={'PASS' if check.passed else 'FAIL'}")

        caught = not observed_pass
        recovered = all("PASS" in item for item in after)
        ok = caught and recovered
        all_good = all_good and ok
        print(
            f"    => 期望 FAIL 的检查：{fault.expect_fail}\n"
            f"    => 实际变红：{observed_fail or '（无！）'}\n"
            f"    => 还原后：{after}\n"
            f"    => {'PASS（判分器抓到了，且可恢复）' if ok else 'FAIL（判分器没抓到或没能恢复）'}"
        )
        results.append(
            {
                "fault_id": fault.fault_id,
                "title": fault.title,
                "what": fault.what,
                "expect_fail": fault.expect_fail,
                "observed_fail": observed_fail,
                "checks_that_stayed_green": observed_pass,
                "after_restore": after,
                "verdict": "PASS" if ok else "FAIL",
                "notes": fault.notes,
            }
        )

    # the submission itself must still be healthy after all that
    print("\n" + "=" * 78)
    print("Final: the untouched submission must still pass every check")
    print("=" * 78)
    final = ca.main()

    lines = [
        "# 故障注入验证 —— 证明验收脚本不是橡皮章",
        "",
        f"生成时间：{datetime.now().isoformat(timespec='seconds')}",
        "",
        "一个永远输出 PASS 的验收脚本没有任何价值。这份记录逐个**故意弄坏**交付物，",
        "断言对应的验收项必须变红（FAIL），再还原并断言它恢复绿色（PASS）。",
        "每一次破坏都在 `finally` 里还原，所以脚本中途失败也不会留下坏状态。",
        "",
        "## 结果总览",
        "",
        "| # | 注入的故障 | 期望变红的验收项 | 实际变红 | 还原后 | 判定 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for index, item in enumerate(results, start=1):
        after = "、".join(item["after_restore"]) or "-"
        observed = "、".join(item["observed_fail"]) or "**无**"
        lines.append(
            f"| {index} | {item['title']} | `{'`、`'.join(item['expect_fail'])}` "
            f"| {observed} | {after} | **{item['verdict']}** |"
        )
    lines += [
        "",
        "## 每条故障的细节",
        "",
    ]
    for index, item in enumerate(results, start=1):
        lines += [
            f"### {index}. {item['title']}",
            "",
            f"- **怎么弄坏的**：{item['what']}",
            f"- **期望变红的验收项**：`{'`、`'.join(item['expect_fail'])}`",
            f"- **实际变红的**：`{'`、`'.join(item['observed_fail']) or '无'}`",
            f"- **还原后**：{ '、'.join(item['after_restore']) }",
            f"- **判定**：**{item['verdict']}**",
        ]
        if item.get("notes"):
            lines.append(f"- 备注：{item['notes']}")
        lines.append("")
    lines += [
        "## 全部还原后的最终验收",
        "",
        "六次破坏全部还原后，交付物回到未受损状态，",
        f"`python -m validation.check_acceptance` 的退出码是 **{final}**（0 表示七项全过）。",
        "",
        "> 这份记录和 `acceptance.md` 一起构成「验收结论可信」的证据：",
        "> 一方面证明交付物满足要求，另一方面证明得出这个结论的脚本在交付物不满足要求时会报警。",
    ]

    target = EVIDENCE_DIR / "fault-injection.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nreport written to {target}")

    print(f"\n{'ALL FAULTS CAUGHT' if all_good else 'SOME FAULTS MISSED'}; final acceptance exit={final}")
    return 0 if all_good and final == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
