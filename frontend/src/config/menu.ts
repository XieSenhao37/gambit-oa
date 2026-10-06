import pages from './pages.json';
export interface MenuNode {
  path: string;
  name: string;
  children?: MenuNode[];
}
// Permissions apply to leaf pages. Group headings survive only when they have visible children.
export function getGroupedMenuData(
  allowedPages: readonly string[],
): MenuNode[] {
  const allowed = new Set(allowedPages);
  const result: MenuNode[] = [];
  for (const page of pages) {
    if (!allowed.has(page.id)) continue;
    const item = { path: page.path, name: page.name };
    if (!page.group) {
      result.push(item);
      continue;
    }
    let group = result.find((node) => node.path === '/' + page.group.id);
    if (!group) {
      group = {
        path: '/' + page.group.id,
        name: page.group.name,
        children: [],
      };
      result.push(group);
    }
    group.children!.push(item);
  }
  return result;
}
