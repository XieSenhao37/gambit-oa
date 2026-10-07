import {
  Children,
  cloneElement,
  isValidElement,
  useState,
  type ReactElement,
} from 'react';
import {
  Bar,
  Legend,
  Line,
  Pie,
  ResponsiveContainer,
  Tooltip,
  YAxis,
} from 'recharts';

interface Choice {
  key: string;
  name: string;
  color: string;
}
// 图形、坐标轴和悬停提示仍由 Recharts 绘制；这里只统一指标选择交互。
export default function InteractiveChart({
  chart,
  initialSelection = 'all',
}: {
  chart: ReactElement;
  initialSelection?: string;
}) {
  const [selection, setSelection] = useState(initialSelection);
  const children = Children.toArray(chart.props.children).filter(
    isValidElement,
  ) as ReactElement[];
  const series = children.filter(
    (child) => child.type === Line || child.type === Bar,
  );
  const pie = children.find((child) => child.type === Pie);
  const pieRows: Record<string, unknown>[] = pie?.props.data ?? [];
  const pieCells = pie
    ? (Children.toArray(pie.props.children).filter(
        isValidElement,
      ) as ReactElement[])
    : [];
  const choices: Choice[] = pie
    ? pieRows.map((row, index) => ({
        key: String(row[pie.props.nameKey]),
        name: String(row[pie.props.nameKey]),
        color: pieCells[index]?.props.fill ?? '#1F4DFF',
      }))
    : series.map((child) => ({
        key: String(child.props.dataKey),
        name: child.props.name,
        color: child.props.stroke ?? child.props.fill,
      }));
  // 切换日期/门店后分类可能消失，自动恢复全部，避免留下空图。
  const selected = choices.some((choice) => choice.key === selection)
    ? selection
    : 'all';
  const visible = series.filter(
    (child) => selected === 'all' || String(child.props.dataKey) === selected,
  );
  const total = pieRows.reduce(
    (sum, row) => sum + Number(row[pie?.props.dataKey] ?? 0),
    0,
  );
  const interactive = choices.length > 1;
  const nextChildren = children.flatMap((child) => {
    if (child.type === Legend) return [];
    if (child.type === Line || child.type === Bar) {
      return [
        cloneElement(child, {
          hide: selected !== 'all' && String(child.props.dataKey) !== selected,
          ...(child.type === Bar
            ? { activeBar: { stroke: '#11132B', strokeWidth: 2 } }
            : { activeDot: { r: 5 } }),
        }),
      ];
    }
    if (child.type === YAxis && series.length) {
      const axis = child.props.yAxisId ?? 0;
      return [
        cloneElement(child, {
          hide: !visible.some((item) => (item.props.yAxisId ?? 0) === axis),
        }),
      ];
    }
    if (child.type === Pie) {
      const indexes = pieRows
        .map((_, index) => index)
        .filter(
          (index) =>
            selected === 'all' ||
            String(pieRows[index][child.props.nameKey]) === selected,
        );
      return [
        cloneElement(child, {
          isAnimationActive: false,
          data: indexes.map((index) => pieRows[index]),
          children: indexes.map((index) => pieCells[index]),
          // 单项仍保留原来扇区的位置和角度，空白部分是其余分类。
          startAngle:
            selected === 'all' || total <= 0
              ? 0
              : (pieRows
                  .slice(0, indexes[0])
                  .reduce(
                    (sum, row) => sum + Number(row[child.props.dataKey] ?? 0),
                    0,
                  ) /
                  total) *
                360,
          endAngle:
            selected === 'all' || total <= 0
              ? 360
              : (pieRows
                  .slice(0, indexes[0] + 1)
                  .reduce(
                    (sum, row) => sum + Number(row[child.props.dataKey] ?? 0),
                    0,
                  ) /
                  total) *
                360,
          // 筛选后占比仍相对于全部分类，不能把选中的分类解释为占比 100%。
          label: false,
        }),
      ];
    }
    if (child.type === Tooltip && pie) {
      return [
        cloneElement(child, {
          formatter: (value: unknown, name: unknown) => {
            const amount = Number(value ?? 0);
            const formatted = child.props.formatter
              ? child.props.formatter(value, name)
              : `${amount.toLocaleString('zh-CN')}${
                  pie.props.dataKey === 'UserCount' ? '人' : ''
                }`;
            return [
              `${formatted}（占全部 ${
                total > 0 ? ((amount / total) * 100).toFixed(1) : '0.0'
              }%）`,
              String(name),
            ];
          },
        }),
      ];
    }
    return [child];
  });
  return (
    <div
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      }}
    >
      {interactive && (
        <div
          role="group"
          aria-label="选择图表指标"
          style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}
        >
          {[{ key: 'all', name: '全部', color: '#1F4DFF' }, ...choices].map(
            (choice) => (
              <button
                key={choice.key}
                type="button"
                aria-pressed={selected === choice.key}
                onClick={() => setSelection(choice.key)}
                style={{
                  cursor: 'pointer',
                  border: `1px solid ${
                    selected === choice.key ? choice.color : '#e5e7eb'
                  }`,
                  borderRadius: 6,
                  padding: '4px 10px',
                  background: selected === choice.key ? '#f0f5ff' : '#fff',
                  color: selected === choice.key ? choice.color : '#6b7280',
                }}
              >
                {choice.key !== 'all' && (
                  <span
                    aria-hidden="true"
                    style={{
                      display: 'inline-block',
                      width: 7,
                      height: 7,
                      borderRadius: '50%',
                      background: choice.color,
                      marginRight: 6,
                    }}
                  />
                )}
                {choice.name}
              </button>
            ),
          )}
        </div>
      )}
      <div style={{ flex: 1, minHeight: 0 }}>
        <ResponsiveContainer width="100%" height="100%">
          {cloneElement(chart, { children: nextChildren })}
        </ResponsiveContainer>
      </div>
    </div>
  );
}
