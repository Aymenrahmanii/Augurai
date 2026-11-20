from augurai.cli import main


def test_version(capsys):
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == "augurai 0.1.0"
