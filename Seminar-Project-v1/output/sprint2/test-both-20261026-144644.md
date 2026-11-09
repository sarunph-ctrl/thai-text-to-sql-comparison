# Sprint 2 — Exploratory comparison

AI-authored synthetic exploratory evaluation, frozen before first execution. Not an independently collected or unbiased benchmark.

| Method | Execution correct | Mean method latency (ms) |
|---|---:|---:|
| rule | 6/10 | 6.382 |
| llm | 10/10 | 3874.181 |

Currency cost remains unknown. This is not an independent benchmark.

## Per-question results

| ID | Question | Rule | LLM |
|---|---|---|---|
| test01 | ขอดูยอดขายรวมในเดือนกันยายน 2569 หน่อยครับ | correct | correct |
| test02 | เดือนกันยายน 2569 ขายของได้เงินรวมเท่าไร | unmatched/wrong | correct |
| test03 | ขอรายได้แยกตามสินค้าในเดือนกันยายน 2569 | correct | correct |
| test04 | เดือนกันยายน 2569 สินค้าแต่ละชนิดขายได้เงินเท่าไร | correct | correct |
| test05 | ขอดูสินค้าขายดีที่สุด 3 อันดับในเดือนกันยายน 2569 | correct | correct |
| test06 | เดือนกันยายน 2569 สินค้ารายใดทำยอดขายสูงสุด 3 อันดับ | unsupported/wrong | correct |
| test07 | ขอดูสินค้าคงเหลือในแต่ละคลังหน่อยครับ | correct | correct |
| test08 | สินค้าแต่ละชนิดคงเหลืออยู่ในแต่ละคลังเท่าไร | unsupported/wrong | correct |
| test09 | ขอดูยอดจ่ายออกสินค้าเดือนกันยายน 2569 | correct | correct |
| test10 | เดือนกันยายน 2569 เบิกสินค้าออกไปแต่ละชนิดกี่ชิ้น | unmatched/wrong | correct |
