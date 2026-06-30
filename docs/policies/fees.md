# Finance policies for fees and exchange

Owner: Finance. Engineering implements these exactly; a change needs Finance's sign-off.

## FP-3: transfer fees

A transfer's fee is a percentage of the amount, in basis points, **rounded half up to the minor
unit**, then raised to the minimum or lowered to the maximum. Transfers below the threshold are free.

| Currency | Free below | Rate | Minimum | Maximum |
| --- | --- | --- | --- | --- |
| USD | 100.00 | 0.25% | 0.10 | 5.00 |
| EUR | 100.00 | 0.25% | 0.10 | 5.00 |
| LBP | 9,000,000.00 | 0.50% | 5,000.00 | 450,000.00 |

Example: 106.00 USD gives 0.265 USD, which rounds half up to 0.27 USD.

## FP-5: exchange

The customer receives `amount x rate x (1 - spread)`, computed exactly and **rounded half to even
at the target currency's minor unit**. A quote fixes that amount for 2 minutes and can be used
once; a conversion made with a quote credits exactly the quoted amount.
