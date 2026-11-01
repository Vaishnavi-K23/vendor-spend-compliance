# Procurement glossary (interview prep)

Plain-language definitions of the terms this project uses, and why each one matters to a business.

| Term | What it means | Why it matters / where it shows up here |
|---|---|---|
| **Purchase order (PO) / contract** | The agreement that says what can be bought, from whom, at what price and up to what amount. | Payments tied to a contract are "on contract". Most payments here join to a contract number. |
| **Award amount / not-to-exceed (NTE)** | The approved spending limit on a contract. | The "spend vs award" KPI. Some awards are only estimates (requirements / blanket / master agreements), so going over isn't automatically a problem. |
| **Modification** | A change to a contract after signing, usually to the amount or scope. | Drives the "contract growth" KPI: how much contracts grow beyond what was originally approved. |
| **Time extension** | A change that moves the contract's end date. | Counted separately; a lot of extensions can mean renewals weren't planned. |
| **Direct voucher (DV) / off-contract ("maverick") spend** | Paying a vendor without any contract behind the purchase. | Headline KPI. It means less negotiated pricing, weaker oversight, and spend that's harder to audit. |
| **Spend under management** | The share of total spend that goes through contracts. | The flip side of off-contract share. Procurement teams are often measured on raising it. |
| **Sole source** | Buying from one vendor without competitive bidding, usually justified by uniqueness. | Less competition can mean higher prices; tracked as a share of dollars. |
| **Emergency procurement** | Fast-tracked buying that skips normal steps because of urgency. | Legitimate in a crisis, but a high share signals poor planning. |
| **Procure-to-pay (P2P)** | The full process: request → PO/contract → receive goods → invoice → payment. | Frames where each check in the project sits. |
| **Three-way match** | Checking that the PO, goods receipt and invoice agree before paying. | Not possible with this data (no receipts or invoice lines), which the README states. With ERP data it's the next step. |
| **Vendor master data** | The organization's list of vendors and their details. | Duplicate or messy vendor records (like "SKYTECH…\|CLEANED-UP") split spend and hide concentration; `dim_vendor` cleans this. |
| **Vendor concentration / HHI** | How much spend depends on a few suppliers. HHI (Herfindahl-Hirschman Index) sums the squared market shares. | High concentration means supplier risk and weaker negotiating position. |
| **Duplicate payment** | Paying the same invoice twice. | Recovering these is real money; the rule flags same vendor + amount within 7 days, then checked by hand. |
| **Contract expiry risk** | A contract ending while the department still needs the goods or service. | Leads to off-contract spend or rushed emergency buys; the expiry calendar gives buyers time to renew or rebid. |

## The one answer to rehearse

**"Why does off-contract spend matter?"**
When money goes out without a contract, the organization loses the prices and terms it negotiated, gets less oversight of who approved the purchase, and makes the spend harder to audit. For a city, that's also a public-accountability issue. My analysis doesn't claim wrongdoing; it flags where to look.
