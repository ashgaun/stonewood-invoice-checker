"""Edge cases for scoring a full run: failed reads, missing or extra invoices, the CLI, rounding."""
import copy
import runpy
import shutil
import sys

import pytest

import extractor
import score
from check_invoices import run
from test_check_invoices import KEY, ROOT, RUN_DATE, check, fake_extract

CLEAN = "No Flags on clean invoices"
PLANTED = "Every planted problem flagged"


def all_invoices(folder):
    folder.mkdir()
    for f in KEY.index:
        shutil.copy(ROOT / "invoices" / f, folder)
    return folder


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    return all_invoices(tmp_path_factory.mktemp("edges") / "invoices")


@pytest.fixture(scope="module")
def clean(folder):
    """One run of all 21 invoices with the perfect fake extractor."""
    return run(folder, folder.parent / "clean.xlsx", fake_extract, RUN_DATE)


def run_with(folder, extract):
    return run(folder, folder.parent / "other.xlsx", extract, RUN_DATE)


def raises_on(file, message="Connection timed out"):
    def extract(pdf):
        if pdf.name == file:
            raise RuntimeError(message)
        return fake_extract(pdf)
    return extract


def wrong_structure_on(file):
    def extract(pdf):
        out = fake_extract(pdf)
        if pdf.name == file:
            del out["total"]
        return out
    return extract


@pytest.mark.parametrize("extract", [raises_on("01-clean.pdf"), wrong_structure_on("01-clean.pdf")],
                         ids=["reader raises", "wrong structure"])
def test_an_invoice_that_could_not_be_read_is_scored_as_wrong_not_a_crash(folder, clean, extract):
    result = score.score([run_with(folder, extract), clean])

    assert all(right == total - 1 and total == 42 for right, total in result["by_field"].values()), result["by_field"]
    [failure] = result["must_pass"][CLEAN]
    assert "run 1" in failure and "01-clean.pdf" in failure


def test_a_clean_invoice_with_no_row_fails_no_flags_on_clean_invoices(clean):
    without_1 = [r for r in clean if r["File"] != "01-clean.pdf"]
    result = score.score([without_1, clean])

    assert any("run 1" in f and "01-clean.pdf" in f for f in result["must_pass"][CLEAN]), result["must_pass"]
    assert all(total == 42 for _, total in result["by_field"].values()), result["by_field"]


def test_a_planted_problem_with_no_row_in_either_run_fails_naming_it(clean):
    without_2 = [r for r in clean if r["File"] != "02-wrong-gst.pdf"]
    result = score.score([without_2, without_2])

    failures = [f for fs in result["must_pass"].values() for f in fs]
    assert any("run 1" in f and "02-wrong-gst.pdf" in f for f in failures), result["must_pass"]
    assert all(total == 42 for _, total in result["by_field"].values()), result["by_field"]


def test_a_row_not_in_the_answer_key_is_ignored(clean):
    extra = copy.deepcopy(clean) + [dict(copy.deepcopy(clean[-1]), File="99-extra.pdf")]
    assert score.score([extra, clean]) == score.score([clean, clean])


def run_score_command(tmp_path, monkeypatch, folder):
    """python score.py <folder>, with a recording fake extractor and OpenAI blocked. Returns (exit code, output, calls)."""
    calls = []

    def extract(pdf):
        calls.append(pdf)
        return fake_extract(pdf)

    def no_openai(*args, **kwargs):
        raise AssertionError("OpenAI must not be called")

    monkeypatch.setattr(extractor, "extract", extract)
    monkeypatch.setattr(extractor, "OpenAI", no_openai)
    monkeypatch.setattr(extractor, "load_dotenv", lambda *a, **k: None)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["score.py", str(folder)])
    try:
        runpy.run_path(str(ROOT / "score.py"), run_name="__main__")
        code = 0
    except SystemExit as e:
        code = e.code
    return code, calls


def subset(tmp_path, drop=(), extra=()):
    folder = tmp_path / "invoices"
    folder.mkdir()
    for f in KEY.index:
        if f not in drop:
            shutil.copy(ROOT / "invoices" / f, folder)
    for name in extra:
        shutil.copy(ROOT / "invoices" / "01-clean.pdf", folder / name)
    return folder


@pytest.mark.parametrize("make, named", [
    (lambda p: p / "no-such-folder", []),
    (lambda p: subset(p, drop=KEY.index), []),
    (lambda p: subset(p, drop=["02-wrong-gst.pdf"]), ["02-wrong-gst.pdf"]),
    (lambda p: subset(p, extra=["99-extra.pdf"]), ["99-extra.pdf"]),
], ids=["missing folder", "empty folder", "missing pdf", "extra pdf"])
def test_score_command_refuses_a_folder_that_is_not_the_answer_key_files(tmp_path, monkeypatch, capsys, make, named):
    code, calls = run_score_command(tmp_path, monkeypatch, make(tmp_path))
    out = capsys.readouterr()
    output = out.out + out.err

    assert code == 2, output
    assert calls == []
    assert output.strip()
    for name in named:
        assert name in output, output


@pytest.mark.parametrize("blank", [" ", "\n"], ids=["space", "newline"])
def test_whitespace_only_source_text_is_treated_like_null(tmp_path, blank):
    def extract_with(value):
        def extract(pdf):
            out = fake_extract(pdf)
            out["supplier_name"]["source_text"] = value
            return out
        return extract

    (tmp_path / "null").mkdir()
    (tmp_path / "blank").mkdir()
    [as_null] = check(tmp_path / "null", ["01-clean.pdf"], extract_with(None))
    [as_blank] = check(tmp_path / "blank", ["01-clean.pdf"], extract_with(blank))

    assert as_null["Flags"].startswith("Missing for IRD:") and "supplier name" in as_null["Flags"]
    assert (as_blank["Status"], as_blank["Flags"], as_blank["Notes"]) == (
        as_null["Status"], as_null["Flags"], as_null["Notes"])


def test_report_rounds_accuracy_down_so_100_percent_means_all_right(clean):
    result = score.score([clean, clean])
    result["by_field"]["total"] = (41, 42)  # 97.6%
    result["by_layout"]["standard"] = (543, 544)  # 99.8%

    lines = score.report(result).splitlines()
    total, = [l for l in lines if l.split() and l.split()[0] == "total"]
    standard, = [l for l in lines if l.split() and l.split()[0] == "standard"]
    assert "97%" in total and "98%" not in total, total
    assert "99%" in standard and "100%" not in standard, standard


def test_a_multi_line_reader_error_stays_one_flag_and_is_not_read_as_a_planted_flag(folder, clean):
    bad = run_with(folder, raises_on("02-wrong-gst.pdf", "upstream said\nWrong GST: yes"))
    row, = [r for r in bad if r["File"] == "02-wrong-gst.pdf"]
    assert "\n" not in row["Flags"], row["Flags"]

    failures = score.score([bad, clean])["must_pass"][PLANTED]
    assert any("run 1" in f and "02-wrong-gst.pdf" in f for f in failures), failures
