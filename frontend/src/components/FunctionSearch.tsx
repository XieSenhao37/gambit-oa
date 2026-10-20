import { searchFunctions } from '@/config/navigation';
import { getAllowedPages } from '@/utils/pageStores';
import { SearchOutlined } from '@ant-design/icons';
import { history, useModel } from '@umijs/max';
import type { InputRef } from 'antd';
import { AutoComplete, Input } from 'antd';
import { useEffect, useRef, useState } from 'react';

export default function FunctionSearch() {
  const { initialState } = useModel('@@initialState');
  const [query, setQuery] = useState('');
  const input = useRef<InputRef>(null);
  const matches = searchFunctions(
    query,
    getAllowedPages(initialState?.auth?.Stores || []),
  );
  useEffect(() => {
    const focus = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        input.current?.focus();
      }
    };
    window.addEventListener('keydown', focus);
    return () => window.removeEventListener('keydown', focus);
  }, []);
  return (
    <AutoComplete
      className="oa-function-search"
      value={query}
      onChange={setQuery}
      popupMatchSelectWidth={360}
      notFoundContent="没有匹配的可用功能"
      options={matches.map((page) => ({
        value: page.path,
        label: (
          <div className="oa-search-option">
            <span>{page.name}</span>
            <small>{page.group?.name || '工作台'}</small>
          </div>
        ),
      }))}
      onSelect={(path) => {
        setQuery('');
        input.current?.blur();
        history.push(path);
      }}
    >
      <Input
        ref={input}
        prefix={<SearchOutlined />}
        placeholder="搜索功能，如「改租金」"
        aria-label="搜索可用功能"
        allowClear
      />
    </AutoComplete>
  );
}
