// basics.js -- the language features our compiler supports, checked against Node.

let a = 10;
let b = 3;
console.log(a + b * 2);          // 16  (precedence)
console.log((a + b) * 2);        // 26  (parentheses)
console.log(a - b - 1);          // 6   (left to right)
console.log(a % b);              // 1
console.log(-a + 4);             // -6

if (a > b) { console.log(1); } else { console.log(0); }
if (a <= b) { console.log(1); } else { console.log(0); }
if (a == 10) { console.log(100); }
if (a != 10) { console.log(999); }

// while loop: 1 + 2 + ... + 100
let sum = 0;
let i = 1;
while (i <= 100) { sum += i; i++; }
console.log(sum);                // 5050

// for loop: 10!
let f = 1;
for (let k = 2; k <= 10; k++) { f *= k; }
console.log(f);                  // 3628800

// count multiples of 3 or 5 up to 30
let count = 0;
for (let n = 1; n <= 30; n++) {
  if (n % 3 == 0) { count++; } else if (n % 5 == 0) { count++; }
}
console.log(count);              // 14

// objects, nested objects, arrays of objects
let p = { x: 3, y: 4, meta: { id: 7 } };
console.log(p.x * p.x + p.y * p.y);   // 25
console.log(p.meta.id);               // 7

let pts = [ { x: 1, y: 2 }, { x: 3, y: 4 }, { x: 5, y: 6 } ];
let total = 0;
for (let j = 0; j < pts.length; j++) { total += pts[j].x + pts[j].y; }
console.log(total);                   // 21
