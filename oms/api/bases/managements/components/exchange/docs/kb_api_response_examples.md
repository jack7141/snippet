# Response examples from KB API

## get_exchangeable_currencies

### success

```json
{
  "account": "32330325601",
  "account_number": "323303256",
  "account_type": "01",
  "tr_code": "SWAM2224",
  "msg": "외화환전 가능금액조회가  완료되었습니다.",
  "exchange_code": "1",
  "apply_exchange_rate": 1200.0,
  "exchange_possible_amt": 0.0,
  "req_amt": 0.0,
  "exchange_amt": 0.0,
  "c_code": "",
  "currencies": [
    {
      "currency_code": "KRW",
      "deposit": 967473.0,
      "exchange_possible_amt": 967473.0
    },
    {
      "currency_code": "USD",
      "deposit": 0.0,
      "exchange_possible_amt": 1000.0
    }
  ]
}
```

## convert_usd_to_krw

### success

```json
{
  "account": "33976875801",
  "account_number": "339768758",
  "account_type": "01",
  "tr_code": "SWAM2224",
  "msg": "외화환전이 완료되었습니다. 감사합니다.",
  "exchange_code": "1",
  "apply_exchange_rate": 1193.0,
  "exchange_possible_amt": 22.48,
  "req_amt": 22.48,
  "exchange_amt": 26818.0,
  "c_code": "",
  "currencies": [
    {
      "currency_code": "KRW",
      "deposit": 655591.0,
      "exchange_possible_amt": 655591.0
    },
    { "currency_code": "USD", "deposit": 22.48, "exchange_possible_amt": 22.48 }
  ]
}
```

### failure

```json
{
  "tr_code": "SWAM2224",
  "account": "32330325601",
  "status": "TRANSMIT_ERROR",
  "msg_code": "7490",
  "msg": "환전신청금액을 확인하세요."
}
```

```json
{
  "tr_code": "SWAM2224",
  "account": "32330401401",
  "status": "TRANSMIT_ERROR",
  "msg_code": "I698",
  "msg": "조회시점과 환전처리시점 환율이 다릅니다.다시 처리하시기 바랍니다."
}
```
