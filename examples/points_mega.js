// points_mega.js -- MEGAMORPHIC: 16 different field orders = 16 shapes,
// more than the 4-slot cache can hold.
let particles = [
  { vy: 0, vx: 1, y: 4, id: 0, mass: 2, x: 3 },
  { mass: 3, x: 4, id: 1, vy: 0, vx: 1, y: 6 },
  { x: 5, y: 8, vy: 0, vx: 1, id: 2, mass: 4 },
  { y: 10, x: 6, vx: 1, id: 3, vy: 0, mass: 2 },
  { id: 4, y: 12, vy: 0, vx: 1, x: 7, mass: 3 },
  { id: 5, y: 14, x: 8, mass: 4, vy: 0, vx: 1 },
  { x: 9, id: 6, mass: 2, vx: 1, vy: 0, y: 16 },
  { id: 7, x: 10, y: 18, vy: 0, mass: 3, vx: 1 },
  { mass: 4, y: 20, id: 8, vx: 1, vy: 0, x: 11 },
  { x: 12, vx: 1, mass: 2, y: 22, vy: 0, id: 9 },
  { vy: 0, mass: 3, id: 10, x: 13, y: 24, vx: 1 },
  { id: 11, y: 26, mass: 4, vy: 0, vx: 1, x: 14 },
  { mass: 2, y: 28, id: 12, vy: 0, vx: 1, x: 15 },
  { vy: 0, vx: 1, mass: 3, x: 16, id: 13, y: 30 },
  { x: 17, id: 14, y: 32, mass: 4, vx: 1, vy: 0 },
  { vy: 0, y: 34, x: 18, id: 15, mass: 2, vx: 1 }
];

let total = 0;
for (let round = 0; round < 2000; round++) {
  for (let i = 0; i < particles.length; i++) {
    let p = particles[i];
    total += p.x * p.x + p.y * p.y;
  }
}
console.log(total);
