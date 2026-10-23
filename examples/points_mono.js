// points_mono.js -- MONOMORPHIC: all 12 objects have the same shape
// (same fields in the same order), so every p.x / p.y site sees 1 shape.
let particles = [
  { id: 0, mass: 2, vx: 1, vy: 0, x: 3, y: 4 },
  { id: 1, mass: 3, vx: 1, vy: 0, x: 4, y: 6 },
  { id: 2, mass: 4, vx: 1, vy: 0, x: 5, y: 8 },
  { id: 3, mass: 2, vx: 1, vy: 0, x: 6, y: 10 },
  { id: 4, mass: 3, vx: 1, vy: 0, x: 7, y: 12 },
  { id: 5, mass: 4, vx: 1, vy: 0, x: 8, y: 14 },
  { id: 6, mass: 2, vx: 1, vy: 0, x: 9, y: 16 },
  { id: 7, mass: 3, vx: 1, vy: 0, x: 10, y: 18 },
  { id: 8, mass: 4, vx: 1, vy: 0, x: 11, y: 20 },
  { id: 9, mass: 2, vx: 1, vy: 0, x: 12, y: 22 },
  { id: 10, mass: 3, vx: 1, vy: 0, x: 13, y: 24 },
  { id: 11, mass: 4, vx: 1, vy: 0, x: 14, y: 26 }
];

let total = 0;
for (let round = 0; round < 2000; round++) {
  for (let i = 0; i < particles.length; i++) {
    let p = particles[i];
    total += p.x * p.x + p.y * p.y;
  }
}
console.log(total);
