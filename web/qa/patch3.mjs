import fs from "node:fs";
const f = new URL("./audit3.mjs", import.meta.url);
let s = fs.readFileSync(f, "utf8");
s = s.replace(',"wrongtype.pdf"]', ']');
s = s.replace('page.posts.push(1)', 'page.posts.push(r.url().replace(/^.*\\/api\\//, ""))');
s = s.replace('posts: page.posts.length', 'posts: page.posts.join(",")');
s = s.replace('"posts", page.posts.length', '"posts", page.posts.join(",")');
fs.writeFileSync(f, s);
