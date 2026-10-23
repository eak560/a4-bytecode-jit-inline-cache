// edge_cases.js -- boundary inputs that must still match Node exactly.

let n = 0;
for (let i = 0; i < 0; i++) { n++; }     // loop body never runs
console.log(n);                            // 0

console.log(-7 + 3);                       // -4  (negative result)
console.log(0 * 12345);                    // 0
console.log(98 / 7);                       // 14  (exact division)

let big = 1;
for (let k = 0; k < 40; k++) { big *= 2; }
console.log(big);                          // 1099511627776  (2^40, large integer)

let deep = { a: { b: { c: { d: 42 } } } };
console.log(deep.a.b.c.d);                 // 42  (four chained property reads)

if (!(3 > 5)) { console.log(1); }          // 1   (negation of a comparison)

let w = 10;
let steps = 0;
while (w > 0) { w -= 3; steps++; }         // 10, 7, 4, 1, -2
console.log(steps);                        // 4

let empty = {};
let one = [ { x: 5 } ];
console.log(one.length + one[0].x);        // 6   (single-element array)
