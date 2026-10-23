// deopt.js -- the loop gets hot on shape A and is compiled (tier 2) with a
// guard "is this shape A?". Halfway through, shape B arrives: the guard fails,
// the compiled code is thrown away (deopt) and the result must still be right.

let items = [
  { a: 1, x: 10 }, { a: 1, x: 10 }, { a: 1, x: 10 }, { a: 1, x: 10 }, { a: 1, x: 10 },
  { a: 1, x: 10 }, { a: 1, x: 10 }, { a: 1, x: 10 }, { a: 1, x: 10 }, { a: 1, x: 10 },
  { x: 20, a: 1 }, { x: 20, a: 1 }, { x: 20, a: 1 }, { x: 20, a: 1 }, { x: 20, a: 1 },
  { x: 20, a: 1 }, { x: 20, a: 1 }, { x: 20, a: 1 }, { x: 20, a: 1 }, { x: 20, a: 1 }
];

let total = 0;
for (let i = 0; i < items.length; i++) {
  total += items[i].x;
  console.log(total);
}
