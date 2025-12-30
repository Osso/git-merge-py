from gitmergepy.runner import main


def test_main():
    main(["tests/files/base.py", "tests/files/current.py", "tests/files/other.py"])
