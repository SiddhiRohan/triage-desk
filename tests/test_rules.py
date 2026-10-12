from app.rules import rule_based_classify

def test_rules_billing():
    res = rule_based_classify("I have a question about my last invoice")
    assert res[0] == "billing"
    assert res[2] <= 0.5

def test_rules_bug():
    res = rule_based_classify("The app crashes whenever I click save")
    assert res[0] == "bug"
    assert res[1] == "high"
    assert res[2] <= 0.5

def test_rules_sales():
    res = rule_based_classify("We are interested in your enterprise pricing")
    assert res[0] == "sales"
    assert res[2] <= 0.5

def test_rules_support():
    res = rule_based_classify("How do I set up my account?")
    assert res[0] == "support"
    assert res[2] <= 0.5

def test_rules_other_vague():
    res = rule_based_classify("Hello there")
    assert res[0] == "other"
    assert res[2] <= 0.5

def test_rules_case_insensitive():
    res = rule_based_classify("BILLING HELP")
    assert res[0] == "billing"
