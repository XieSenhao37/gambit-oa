import logo from '@/assets/logo.png';
import { authStatus, login, sendCode } from '@/services/auth';
import { Alert, Button, Form, Input, message, Space } from 'antd';
import { useEffect, useState } from 'react';

export default function LoginPage() {
  const [form] = Form.useForm();
  const [mode, setMode] = useState<'password' | 'sms'>();
  const [statusError, setStatusError] = useState(false);
  const expired =
    new URLSearchParams(window.location.search).get('reason') === 'expired' ||
    sessionStorage.getItem('oa_session_expired') === '1';
  const [ready, setReady] = useState(false),
    [sending, setSending] = useState(false),
    [loading, setLoading] = useState(false);
  const [challenge, setChallenge] = useState(''),
    [sentPhone, setSentPhone] = useState(''),
    [count, setCount] = useState(0);
  useEffect(() => {
    let active = true;
    authStatus()
      .then((r) => {
        if (!active) return;
        if (!r.Data) throw Error();
        setReady(!!r.Data.SmsReady);
        setMode(r.Data.LoginMode || 'sms');
      })
      .catch(() => {
        if (active) setStatusError(true);
      });
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    if (!count) return;
    const timer = setTimeout(() => setCount(count - 1), 1000);
    return () => clearTimeout(timer);
  }, [count]);
  const send = async () => {
    const { phone } = await form.validateFields(['phone']);
    setSending(true);
    try {
      const r = await sendCode(phone);
      if (!r.Data) throw Error();
      setChallenge(r.Data.ChallengeId);
      setSentPhone(phone);
      setCount(r.Data.RetryAfter);
      message.success('验证码已发送');
    } finally {
      setSending(false);
    }
  };
  const submit = async (values: {
    username: string;
    password: string;
    phone: string;
    code: string;
  }) => {
    if (!mode) return;
    if (mode === 'sms' && (!challenge || values.phone !== sentPhone)) {
      message.warning('请先获取该手机号的验证码');
      return;
    }
    setLoading(true);
    try {
      const r = await login(
        mode === 'password'
          ? { username: values.username, password: values.password }
          : { ChallengeId: challenge, Code: values.code },
      );
      if (!r.Data) throw Error();
      localStorage.setItem('token', r.Data.token);
      sessionStorage.removeItem('oa_session_expired');
      localStorage.removeItem('role');
      window.location.replace('/');
    } catch {
      // The shared request handler displays the server's error; never log credentials.
    } finally {
      setLoading(false);
    }
  };
  return (
    <div style={{ maxWidth: 420, margin: '10vh auto', padding: 28 }}>
      <div style={{ textAlign: 'center' }}>
        <img src={logo} alt="Gambit" width={100} />
        <h2>GAMBIT OA</h2>
        <p>{mode === 'sms' ? '员工手机号验证码登录' : '管理员账号登录'}</p>
      </div>
      {expired && (
        <Alert
          type="warning"
          showIcon
          message="登录已过期或已失效，请重新登录"
          style={{ marginBottom: 16 }}
        />
      )}
      {statusError && (
        <Alert
          type="error"
          showIcon
          message="无法读取登录配置"
          description="请刷新页面后重试。"
          action={
            <Button onClick={() => window.location.reload()}>刷新</Button>
          }
          style={{ marginBottom: 16 }}
        />
      )}
      {mode === 'password' && (
        <Alert
          type="info"
          showIcon
          message="临时账号登录"
          description="短信服务审核期间，请使用管理员账号和密码登录。"
          style={{ marginBottom: 24 }}
        />
      )}
      {mode === 'sms' && !ready && (
        <Alert
          type="info"
          showIcon
          message="短信登录尚未开通"
          description="短信服务配置完成后即可使用。请联系总部管理员。"
          style={{ marginBottom: 24 }}
        />
      )}
      <Form
        form={form}
        layout="vertical"
        onFinish={submit}
        initialValues={{ username: 'admin' }}
      >
        {mode === 'password' && (
          <>
            <Form.Item
              name="username"
              label="账号"
              rules={[
                { required: true, whitespace: true, message: '请输入账号' },
              ]}
            >
              <Input size="large" autoComplete="username" maxLength={64} />
            </Form.Item>
            <Form.Item
              name="password"
              label="密码"
              rules={[{ required: true, message: '请输入密码' }]}
            >
              <Input.Password
                size="large"
                autoComplete="current-password"
                maxLength={128}
              />
            </Form.Item>
          </>
        )}
        {mode === 'sms' && (
          <>
            <Form.Item
              name="phone"
              label="员工手机号"
              rules={[
                {
                  required: true,
                  pattern: /^1[3-9]\d{9}$/,
                  message: '请输入正确的手机号',
                },
              ]}
            >
              <Input size="large" autoComplete="tel" maxLength={11} />
            </Form.Item>
            <Form.Item label="短信验证码">
              <Space.Compact block>
                <Form.Item
                  name="code"
                  noStyle
                  rules={[
                    {
                      required: true,
                      pattern: /^\d{6}$/,
                      message: '请输入六位验证码',
                    },
                  ]}
                >
                  <Input
                    size="large"
                    autoComplete="one-time-code"
                    maxLength={6}
                  />
                </Form.Item>
                <Button
                  size="large"
                  disabled={!ready || count > 0}
                  loading={sending}
                  onClick={() => send().catch(() => {})}
                >
                  {count ? `${count} 秒后重发` : '获取验证码'}
                </Button>
              </Space.Compact>
            </Form.Item>
          </>
        )}
        <Button
          block
          size="large"
          type="primary"
          htmlType="submit"
          loading={loading || (!mode && !statusError)}
          disabled={!mode || (mode === 'sms' && !ready)}
        >
          登录
        </Button>
        <p style={{ color: '#888', marginTop: 16 }}>
          {mode === 'password'
            ? '管理员拥有全部门店及管理页面权限。登录有效期为 15 天。'
            : '仅限已开通门店授权的员工。账号开通或手机号变更请联系总部管理员。'}
        </p>
      </Form>
    </div>
  );
}
