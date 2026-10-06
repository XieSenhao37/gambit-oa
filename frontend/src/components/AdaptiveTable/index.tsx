import {
  ProTable as BaseProTable,
  type ProTableProps,
} from '@ant-design/pro-components';
import { Table as BaseTable, type TableProps } from 'antd';
import { fitColumns, fitScrollWidth } from './columns';
import './index.less';

export function ProTable<
  T extends Record<string, any>,
  P extends Record<string, any> = Record<string, any>,
  V = 'text',
>(props: ProTableProps<T, P, V>) {
  const { columns, width } = fitColumns(props.columns);
  return (
    <BaseProTable<T, P, V>
      size="middle"
      {...props}
      className={`oa-adaptive-table ${props.className || ''}`}
      columns={columns}
      tableLayout={props.tableLayout ?? 'fixed'}
      rowSelection={
        props.rowSelection
          ? { columnWidth: 48, ...props.rowSelection }
          : props.rowSelection
      }
      expandable={
        props.expandable ? { columnWidth: 64, ...props.expandable } : undefined
      }
      scroll={{
        ...props.scroll,
        x: fitScrollWidth(
          width,
          props.scroll?.x,
          !!props.rowSelection,
          !!props.expandable,
        ),
      }}
    />
  );
}

export function Table<T extends object = any>(props: TableProps<T>) {
  const { columns, width } = fitColumns(props.columns);
  return (
    <BaseTable<T>
      size="middle"
      {...props}
      className={`oa-adaptive-table ${props.className || ''}`}
      columns={columns}
      tableLayout={props.tableLayout ?? 'fixed'}
      rowSelection={
        props.rowSelection
          ? { columnWidth: 48, ...props.rowSelection }
          : undefined
      }
      expandable={
        props.expandable ? { columnWidth: 64, ...props.expandable } : undefined
      }
      scroll={{
        ...props.scroll,
        x: fitScrollWidth(
          width,
          props.scroll?.x,
          !!props.rowSelection,
          !!props.expandable,
        ),
      }}
    />
  );
}
