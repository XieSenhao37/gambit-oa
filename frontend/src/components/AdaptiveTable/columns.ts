/** Shared pixel widths keep unconstrained columns from collapsing on tablets. */
export interface LayoutColumn {
  title?: unknown;
  width?: number | string;
  hideInTable?: boolean;
  hidden?: boolean;
  valueType?: unknown;
  children?: LayoutColumn[];
}

export function fitColumns<T extends LayoutColumn>(
  columns?: T[],
): {
  columns: T[] | undefined;
  width: number;
} {
  let width = 0;
  const fitted = columns?.map((column) => {
    if (column.hideInTable || column.hidden) return column;
    if (column.children?.length) {
      const children = fitColumns(column.children);
      width += children.width;
      return { ...column, children: children.columns };
    }
    const title = typeof column.title === 'string' ? column.title : '';
    const specified =
      typeof column.width === 'number'
        ? column.width
        : /^\d+(px)?$/.test(column.width || '')
        ? parseInt(column.width!, 10)
        : 0;
    const fallback =
      column.valueType === 'option' || /操作/.test(title)
        ? 200
        : /信息|名称|备注|原因|内容/.test(title)
        ? 240
        : 160;
    const columnWidth = Math.max(specified || fallback, title.length * 14 + 32);
    width += columnWidth;
    return { ...column, width: columnWidth };
  });
  return { columns: fitted as T[] | undefined, width };
}

export function fitScrollWidth(
  width: number,
  requested: unknown,
  selection: boolean,
  expanded: boolean,
) {
  const minimum = width + (selection ? 48 : 0) + (expanded ? 64 : 0);
  return typeof requested === 'number'
    ? Math.max(minimum, requested)
    : minimum || 'max-content';
}
