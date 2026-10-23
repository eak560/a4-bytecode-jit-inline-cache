// points_poly.js -- POLYMORPHIC: same fields, 3 different orders = 3 shapes.
// Fits in the inline cache's 4 slots.
let particles = [
  { id: 0, mass: 2, vx: 1, vy: 0, x: 3, y: 4 },
  { x: 4, y: 6, id: 1, mass: 3, vx: 1, vy: 0 },
  { vy: 0, vx: 1, mass: 4, id: 2, y: 8, x: 5 },
  { id: 3, mass: 2, vx: 1, vy: 0, x: 6, y: 10 },
  { x: 7, y: 12, id: 4, mass: 3, vx: 1, vy: 0 },
  { vy: 0, vx: 1, mass: 4, id: 5, y: 14, x: 8 },
  { id: 6, mass: 2, vx: 1, vy: 0, x: 9, y: 16 },
  { x: 10, y: 18, id: 7, mass: 3, vx: 1, vy: 0 },
  { vy: 0, vx: 1, mass: 4, id: 8, y: 20, x: 11 },
  { id: 9, mass: 2, vx: 1, vy: 0, x: 12, y: 22 },
  { x: 13, y: 24, id: 10, mass: 3, vx: 1, vy: 0 },
  { vy: 0, vx: 1, mass: 4, id: 11, y: 26, x: 14 }
];

let total = 0;
for (let round = 0; round < 2000; round++) {
  for (let i = 0; i < particles.length; i++) {
    let p = particles[i];
    total += p.x * p.x + p.y * p.y;
  }
}
console.log(total);
