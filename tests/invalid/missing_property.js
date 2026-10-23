// Reads a property the object does not have. (Node prints undefined; our VM reports an error.)
let p = { x: 1 };
console.log(p.y);
