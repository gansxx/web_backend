// Setup type definitions for built-in Supabase Runtime APIs
import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const RESEND_API_KEY = Deno.env.get('RESEND_API_KEY');

// Encode display name using RFC 2047 (MIME encoded-word) format
// This allows non-ASCII characters in email headers
function encodeDisplayName(displayName: string): string {
  // Convert to UTF-8 bytes and then to base64
  const utf8Bytes = new TextEncoder().encode(displayName);
  const base64 = btoa(String.fromCharCode(...utf8Bytes));

  // RFC 2047 format: =?charset?encoding?encoded-text?=
  // B = Base64 encoding
  return `=?UTF-8?B?${base64}?=`;
}

// Format database change notification email with fixed parameters
function formatNotificationEmail(payload: any, params: { html?: string }): { to: string; subject: string; html: string } {
  const { type, table, record, old_record, schema } = payload;

  // Fixed parameters for webhook notifications
  const to = '1214250247@qq.com';
  const subject = 'database webhook';

  // Generate HTML content - use custom template or default
  let html: string;
  if (params.html) {
    // Replace placeholders in custom HTML template
    html = params.html
      .replace(/\{\{type\}\}/g, type)
      .replace(/\{\{table\}\}/g, table)
      .replace(/\{\{schema\}\}/g, schema || 'public')
      .replace(/\{\{timestamp\}\}/g, new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }))
      .replace(/\{\{record\}\}/g, JSON.stringify(record, null, 2))
      .replace(/\{\{old_record\}\}/g, old_record ? JSON.stringify(old_record, null, 2) : 'N/A');
  } else {
    // Default HTML template
    html = `
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
      <h2 style="color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px;">
        数据库变更通知
      </h2>

      <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
        <p><strong>事件类型:</strong> <span style="color: #4CAF50;">${type}</span></p>
        <p><strong>表名:</strong> ${table}</p>
        <p><strong>Schema:</strong> ${schema || 'public'}</p>
        <p><strong>时间:</strong> ${new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}</p>
      </div>

      ${type !== 'DELETE' ? `
        <div style="margin: 20px 0;">
          <h3 style="color: #333;">新记录数据:</h3>
          <pre style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; overflow-x: auto;">${JSON.stringify(record, null, 2)}</pre>
        </div>
      ` : ''}

      ${type === 'UPDATE' && old_record ? `
        <div style="margin: 20px 0;">
          <h3 style="color: #333;">旧记录数据:</h3>
          <pre style="background-color: #fff3cd; padding: 15px; border-radius: 5px; overflow-x: auto;">${JSON.stringify(old_record, null, 2)}</pre>
        </div>
      ` : ''}

      ${type === 'DELETE' && old_record ? `
        <div style="margin: 20px 0;">
          <h3 style="color: #333;">已删除记录:</h3>
          <pre style="background-color: #f8d7da; padding: 15px; border-radius: 5px; overflow-x: auto;">${JSON.stringify(old_record, null, 2)}</pre>
        </div>
      ` : ''}

      <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 12px;">
        <p>此邮件由 Z加速 系统自动发送，请勿回复。</p>
      </div>
    </div>
  `;
  }

  return { to, subject, html };
}

Deno.serve(async (req) => {
  try {
    const payload = await req.json();

    // Handle both direct calls and Supabase webhook events
    let to: string;
    let subject: string;
    let html: string;

    // Check if this is a Supabase webhook event
    if (payload.type && payload.table) {
      // Webhook event format - uses fixed parameters (to: 1214250247@qq.com, subject: database webhook)
      const params = {
        html: payload.html        // Optional: custom HTML template
      };

      // Format notification email content with fixed parameters
      const emailContent = formatNotificationEmail(payload, params);
      to = emailContent.to;
      subject = emailContent.subject;
      html = emailContent.html;

      console.log(`Webhook event received: ${payload.type} on ${payload.table}, sending to ${to}`);
    } else if (payload.to && payload.subject && payload.html) {
      // Direct API call format - for custom notifications
      to = payload.to;
      subject = payload.subject;
      html = payload.html;

      console.log(`Direct API call: sending to ${to}`);
    } else {
      // Invalid payload format
      return new Response(
        JSON.stringify({
          error: 'Invalid payload format',
          message: 'Expected either webhook event (type, table, record) or direct call (to, subject, html)',
          payload_received: payload
        }),
        { status: 400, headers: { 'Content-Type': 'application/json' } }
      );
    }

    // Validate required fields
    if (!to || !subject || !html) {
      return new Response(
        JSON.stringify({
          error: 'Missing required fields',
          missing: {
            to: !to,
            subject: !subject,
            html: !html
          }
        }),
        { status: 400, headers: { 'Content-Type': 'application/json' } }
      );
    }

    // Encode the display name "Z加速" to RFC 2047 format
    const encodedDisplayName = encodeDisplayName('Z加速');
    const fromAddress = `${encodedDisplayName} <noreply@emailsend.selfgo.asia>`;

    // Send email via Resend
    const res = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${RESEND_API_KEY}`
      },
      body: JSON.stringify({
        from: fromAddress,
        to,
        subject,
        html
      })
    });

    const data = await res.json();

    if (res.ok) {
      console.log(`Email sent successfully to ${to}`);
    } else {
      console.error(`Failed to send email: ${JSON.stringify(data)}`);
    }

    return new Response(JSON.stringify(data), {
      status: res.ok ? 200 : res.status,
      headers: {
        'Content-Type': 'application/json'
      }
    });
  } catch (error) {
    console.error('Error processing request:', error);
    return new Response(
      JSON.stringify({
        error: 'Internal server error',
        message: error.message
      }),
      { status: 500, headers: { 'Content-Type': 'application/json' } }
    );
  }
});
