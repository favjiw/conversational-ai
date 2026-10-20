import React, { useState } from 'react';

// Status antrean dari backend (app/comments/queue.py) → label operator.
const STATUS = {
  classifying: { label: 'Diklasifikasi…', cls: 'bg-gray-100 text-gray-600' },
  waiting: { label: 'Menunggu', cls: 'bg-amber-100 text-amber-800' },
  scheduled: { label: 'Dijadwalkan', cls: 'bg-blue-100 text-blue-800' },
  played: { label: 'Diputar', cls: 'bg-emerald-100 text-emerald-800' },
  rejected: { label: 'Ditolak', cls: 'bg-rose-100 text-rose-800' },
  unavailable: { label: 'Tidak tersedia', cls: 'bg-orange-100 text-orange-800' },
  general: { label: 'Komentar', cls: 'bg-slate-100 text-slate-600' },
  read: { label: 'Dibacakan', cls: 'bg-violet-100 text-violet-800' },
};

const SERVICE = {
  ready: { label: 'Rekomendasi siap', cls: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  loading: { label: 'Memuat rekomendasi…', cls: 'bg-amber-50 text-amber-700 border-amber-200' },
  disabled: { label: 'Rekomendasi nonaktif', cls: 'bg-gray-50 text-gray-500 border-gray-200' },
  error: { label: 'Rekomendasi error', cls: 'bg-rose-50 text-rose-700 border-rose-200' },
};

export default function CommentPanel({ commentQueue, submitComment }) {
  const [username, setUsername] = useState('');
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const [message, setMessage] = useState(null);

  const service = commentQueue?.recommender;
  const serviceInfo = SERVICE[service?.status] || SERVICE.disabled;
  const comments = commentQueue?.comments || [];

  const onSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim() || !text.trim()) return;
    setSending(true);
    const error = await submitComment(username.trim(), text.trim());
    setSending(false);
    setMessage(error);
    if (!error) setText('');
  };

  return (
    <section className="bg-white rounded-2xl border border-gray-200/90 p-7 shadow-xs">
      <div className="flex items-center justify-between pb-4 border-b border-gray-100 gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-bold text-gray-900">Komentar Penonton</h2>
          <span className="bg-gray-100 text-gray-500 text-[11px] font-medium px-2 py-0.5 rounded">Input operator</span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span
            className={`border px-2 py-0.5 rounded-full font-medium ${serviceInfo.cls}`}
            title={service?.reason || service?.model || ''}
          >
            {serviceInfo.label}
            {service?.status === 'disabled' && service?.reason ? ` (${service.reason})` : ''}
          </span>
          <span className="text-gray-400">{commentQueue?.waiting || 0} request menunggu</span>
        </div>
      </div>

      <form onSubmit={onSubmit} className="flex flex-wrap gap-2 pt-4">
        <input
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="username"
          maxLength={64}
          className="w-40 px-3 py-2 text-sm rounded-lg border border-gray-200 focus:outline-none focus:border-gray-400"
        />
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="isi komentar, mis. kak puterin hati2 dijalan tulus dong"
          maxLength={300}
          className="flex-1 min-w-[220px] px-3 py-2 text-sm rounded-lg border border-gray-200 focus:outline-none focus:border-gray-400"
        />
        <button
          type="submit"
          disabled={sending || !username.trim() || !text.trim()}
          className="px-4 py-2 text-sm font-semibold rounded-lg bg-gray-900 text-white disabled:opacity-40"
        >
          {sending ? 'Mengirim…' : 'Kirim'}
        </button>
      </form>
      {message && <p className="text-xs text-rose-600 mt-2">{message}</p>}

      <div className="mt-4 max-h-[320px] overflow-y-auto space-y-2 pr-1">
        {comments.length === 0 ? (
          <p className="text-sm text-gray-400 py-6 text-center">Belum ada komentar.</p>
        ) : (
          comments.map((c) => {
            const st = STATUS[c.status] || STATUS.general;
            return (
              <div key={c.id} className="flex items-start gap-3 text-sm border border-gray-100 rounded-lg px-3 py-2">
                <span className={`shrink-0 text-[11px] font-semibold px-2 py-0.5 rounded ${st.cls}`}>
                  {st.label}
                  {c.slot_id && ['scheduled', 'played', 'read'].includes(c.status) ? ` ${c.slot_id}` : ''}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-gray-800 break-words">
                    <span className="font-semibold">@{c.username}</span> {c.text}
                  </p>
                  {c.song && (
                    <p className="text-xs text-gray-500 mt-0.5">
                      ♪ {c.song.title} — {c.song.artist}
                    </p>
                  )}
                  {c.note && <p className="text-[11px] text-gray-400 mt-0.5">{c.note}</p>}
                </div>
                {c.timings?.total != null && (
                  <span className="shrink-0 text-[11px] font-mono text-gray-400">{c.timings.total.toFixed(1)} s</span>
                )}
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}
