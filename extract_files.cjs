const fs = require('fs');
const path = require('path');

const guidePath = 'C:\\Users\\golde\\Desktop\\Projects\\Home Quest\\IMPLEMENTATION_GUIDE_PART5_ONWARDS.md';
const content = fs.readFileSync(guidePath, 'utf-8');

const regex = /```(?:typescript|tsx?)\s*\n\/\/\s*(src\/[^\n]+)\n([\s\S]*?)```/g;
let match;
while ((match = regex.exec(content)) !== null) {
  let relativePath = match[1].trim();
  const code = '// ' + relativePath + '\n' + match[2];
  
  // Clean up any extra comments the author added in parentheses like `// src/domains/... (modify)`
  relativePath = relativePath.split('(')[0].trim();
  
  const fullPath = path.join('C:\\Users\\golde\\Desktop\\Projects\\Home Quest', relativePath);
  const dir = path.dirname(fullPath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  
  // we only want to write Part 7 onwards (and maybe rewrite Part 5/6 to ensure it's exact)
  // Let's just write everything that matches. It overwrites correctly.
  fs.writeFileSync(fullPath, code);
  console.log('Wrote', fullPath);
}
