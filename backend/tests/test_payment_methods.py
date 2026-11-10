from app.payment_methods import normalise_payment_method


def test_old_native_methods_merge_with_web_methods_without_changing_stripe():
    assert normalise_payment_method("card") == normalise_payment_method("eftpos") == "eftpos"
    assert normalise_payment_method("bank_transfer") == normalise_payment_method("bank") == "bank"
    assert normalise_payment_method(" CASH ") == "cash"
    assert normalise_payment_method("stripe") == "stripe"
    assert normalise_payment_method("") is None
