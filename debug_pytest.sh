
python3 -m pdb -c "b pytest.main" -c "c" -c "p sys.last_type, sys.last_value, sys.last_traceback" tests/temp_test.py --collect-only
