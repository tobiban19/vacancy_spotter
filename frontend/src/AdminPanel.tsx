import React, { useEffect, useState } from 'react';
import {
  Users,
  Search,
  RefreshCw,
  ShieldCheck,
  CheckCircle,
  XCircle,
  Clock,
  Tv,
  X,
  Plus,
  Ban,
  UserCheck,
  Loader2,
  BadgeAlert,
} from 'lucide-react';
import { api, AdminStats, AdminUser, AdminUserDetail } from './api';

interface AdminPanelProps {
  onClose?: () => void;
}

export const AdminPanel: React.FC<AdminPanelProps> = () => {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [pages, setPages] = useState<number>(1);
  const [search, setSearch] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Selected User Modal State
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [userDetail, setUserDetail] = useState<AdminUserDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState<boolean>(false);
  const [banReason, setBanReason] = useState<string>('');
  const [updatingSub, setUpdatingSub] = useState<boolean>(false);
  const [updatingBan, setUpdatingBan] = useState<boolean>(false);
  const [modalTab, setModalTab] = useState<'profile' | 'channels' | 'sub' | 'ban'>('profile');

  const loadData = async (isRef = false) => {
    if (isRef) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const [statsRes, usersRes] = await Promise.all([
        api.getAdminStats(),
        api.getAdminUsers(page, 15, search, statusFilter),
      ]);
      setStats(statsRes);
      setUsers(usersRes.items);
      setTotal(usersRes.total);
      setPages(usersRes.pages);
    } catch (err: any) {
      setError(err.message || 'Ошибка загрузки данных админ-панели');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [page, statusFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    loadData();
  };

  const handleOpenUser = async (userId: number) => {
    setSelectedUserId(userId);
    setLoadingDetail(true);
    setUserDetail(null);
    setModalTab('profile');
    try {
      const detail = await api.getAdminUserDetail(userId);
      setUserDetail(detail);
      setBanReason(detail.ban_reason || '');
    } catch (err: any) {
      alert(`Ошибка загрузки деталей: ${err.message}`);
      setSelectedUserId(null);
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleUpdateSubscription = async (action: 'add_days' | 'set_status' | 'revoke', days?: number) => {
    if (!selectedUserId) return;
    setUpdatingSub(true);
    try {
      await api.updateAdminUserSubscription(selectedUserId, { action, days });
      // Reload user details & list
      const updated = await api.getAdminUserDetail(selectedUserId);
      setUserDetail(updated);
      loadData(true);
    } catch (err: any) {
      alert(`Ошибка обновления подписки: ${err.message}`);
    } finally {
      setUpdatingSub(false);
    }
  };

  const handleToggleBan = async (isBanned: boolean) => {
    if (!selectedUserId) return;
    setUpdatingBan(true);
    try {
      await api.updateAdminUserBan(selectedUserId, { is_banned: isBanned, ban_reason: banReason });
      const updated = await api.getAdminUserDetail(selectedUserId);
      setUserDetail(updated);
      loadData(true);
    } catch (err: any) {
      alert(`Ошибка обновления статуса бана: ${err.message}`);
    } finally {
      setUpdatingBan(false);
    }
  };

  const getSubBadge = (status: string, isBanned: boolean) => {
    if (isBanned) {
      return (
        <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-red-100 text-red-700 border border-red-200 flex items-center gap-1 w-max">
          <Ban size={10} /> Забанен
        </span>
      );
    }
    switch (status) {
      case 'active':
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-100 text-emerald-700 border border-emerald-200 flex items-center gap-1 w-max">
            <CheckCircle size={10} /> Активна
          </span>
        );
      case 'demo':
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-100 text-blue-700 border border-blue-200 flex items-center gap-1 w-max">
            <Clock size={10} /> Демо
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-100 text-amber-700 border border-amber-200 flex items-center gap-1 w-max">
            <XCircle size={10} /> Истекла
          </span>
        );
    }
  };

  return (
    <div className="space-y-4 pb-20">
      {/* Header */}
      <div className="flex items-center justify-between bg-gradient-to-r from-slate-900 to-slate-800 text-white p-4 rounded-2xl shadow-md">
        <div>
          <h2 className="text-lg font-bold flex items-center gap-2">
            <ShieldCheck className="text-emerald-400" size={20} />
            <span>Панель Администратора</span>
          </h2>
          <p className="text-xs text-slate-300">Управление пользователями, подписками и чатами</p>
        </div>
        <button
          onClick={() => loadData(true)}
          disabled={refreshing}
          className="p-2 bg-white/10 hover:bg-white/20 rounded-xl transition-all text-white active:scale-95"
          title="Обновить"
        >
          <RefreshCw size={16} className={refreshing ? 'animate-spin' : ''} />
        </button>
      </div>

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-600 text-xs flex items-center gap-2">
          <BadgeAlert size={16} />
          <span>{error}</span>
        </div>
      )}

      {/* Stats Cards Grid */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
          <div className="bg-white p-3 rounded-xl border border-slate-100 shadow-sm flex items-center gap-3">
            <div className="p-2 bg-blue-50 text-blue-600 rounded-lg">
              <Users size={18} />
            </div>
            <div>
              <div className="text-[10px] text-slate-400 font-medium">Всего юзеров</div>
              <div className="text-base font-bold text-slate-900">{stats.total_users}</div>
            </div>
          </div>

          <div className="bg-white p-3 rounded-xl border border-slate-100 shadow-sm flex items-center gap-3">
            <div className="p-2 bg-emerald-50 text-emerald-600 rounded-lg">
              <CheckCircle size={18} />
            </div>
            <div>
              <div className="text-[10px] text-slate-400 font-medium">Платные подписки</div>
              <div className="text-base font-bold text-emerald-600">{stats.active_paid_users}</div>
            </div>
          </div>

          <div className="bg-white p-3 rounded-xl border border-slate-100 shadow-sm flex items-center gap-3">
            <div className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
              <Clock size={18} />
            </div>
            <div>
              <div className="text-[10px] text-slate-400 font-medium">Демо доступ</div>
              <div className="text-base font-bold text-indigo-600">{stats.demo_users}</div>
            </div>
          </div>

          <div className="bg-white p-3 rounded-xl border border-slate-100 shadow-sm flex items-center gap-3">
            <div className="p-2 bg-red-50 text-red-600 rounded-lg">
              <Ban size={18} />
            </div>
            <div>
              <div className="text-[10px] text-slate-400 font-medium">Забанено</div>
              <div className="text-base font-bold text-red-600">{stats.banned_users}</div>
            </div>
          </div>
        </div>
      )}

      {/* Search & Filters */}
      <div className="bg-white p-3 rounded-xl border border-slate-100 shadow-sm space-y-3">
        <form onSubmit={handleSearchSubmit} className="flex gap-2">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Поиск по ID, username, имени..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200 pl-8 pr-3 py-2 rounded-lg text-xs font-body focus:outline-none focus:border-blue-500"
            />
          </div>
          <button
            type="submit"
            className="px-3.5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-medium transition-all"
          >
            Искать
          </button>
        </form>

        {/* Filter Pills */}
        <div className="flex gap-1.5 overflow-x-auto pb-1 no-scrollbar">
          {[
            { id: 'all', label: 'Все' },
            { id: 'active', label: 'Активные' },
            { id: 'demo', label: 'Демо' },
            { id: 'expired', label: 'Истекли' },
            { id: 'banned', label: 'Забанены' },
          ].map((f) => (
            <button
              key={f.id}
              onClick={() => {
                setStatusFilter(f.id);
                setPage(1);
              }}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-all whitespace-nowrap ${
                statusFilter === f.id
                  ? 'bg-slate-900 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Users Table / Cards */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-slate-400 text-xs flex flex-col items-center gap-2">
            <Loader2 size={24} className="animate-spin text-blue-600" />
            <span>Загрузка списка пользователей...</span>
          </div>
        ) : users.length === 0 ? (
          <div className="p-8 text-center text-slate-400 text-xs">
            Пользователи не найдены.
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {users.map((u) => (
              <div
                key={u.user_id}
                onClick={() => handleOpenUser(u.user_id)}
                className="p-3 hover:bg-slate-50 transition-all cursor-pointer flex items-center justify-between gap-3"
              >
                <div className="space-y-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-xs text-slate-900 truncate">
                      {u.first_name}
                    </span>
                    {u.username && (
                      <span className="text-[11px] text-blue-600 font-mono">
                        @{u.username}
                      </span>
                    )}
                    <span className="text-[10px] text-slate-400 font-mono">
                      ID: {u.user_id}
                    </span>
                  </div>

                  <div className="flex items-center gap-2 text-[11px] text-slate-500 flex-wrap">
                    <span>🎬 {u.profession_id}</span>
                    <span>•</span>
                    <span className="flex items-center gap-1">
                      <Tv size={10} /> {u.channels_count} чат(ов)
                    </span>
                  </div>
                </div>

                <div className="flex flex-col items-end gap-1 flex-shrink-0">
                  {getSubBadge(u.subscription_status, u.is_banned)}
                  <span className="text-[10px] text-slate-400">
                    {u.subscription_until
                      ? `до ${new Date(u.subscription_until).toLocaleDateString('ru-RU')}`
                      : `демо до ${new Date(u.demo_until).toLocaleDateString('ru-RU')}`}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Pagination */}
        {pages > 1 && (
          <div className="p-3 bg-slate-50 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
            <span>Страница {page} из {pages} (Всего: {total})</span>
            <div className="flex gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="px-2.5 py-1 bg-white border border-slate-200 rounded-md disabled:opacity-40"
              >
                Назад
              </button>
              <button
                disabled={page >= pages}
                onClick={() => setPage((p) => p + 1)}
                className="px-2.5 py-1 bg-white border border-slate-200 rounded-md disabled:opacity-40"
              >
                Вперед
              </button>
            </div>
          </div>
        )}
      </div>

      {/* User Details Drawer / Modal */}
      {selectedUserId && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-end sm:items-center justify-center p-0 sm:p-4">
          <div className="bg-white w-full sm:max-w-xl max-h-[90vh] rounded-t-2xl sm:rounded-2xl flex flex-col overflow-hidden shadow-2xl animate-in fade-in slide-in-from-bottom-5">
            {/* Modal Header */}
            <div className="p-4 bg-slate-900 text-white flex items-center justify-between">
              <div>
                <h3 className="font-bold text-sm flex items-center gap-2">
                  <span>Карточка Пользователя</span>
                  <span className="text-xs text-slate-400 font-mono">#{selectedUserId}</span>
                </h3>
              </div>
              <button
                onClick={() => setSelectedUserId(null)}
                className="p-1 hover:bg-white/20 rounded-lg transition-all"
              >
                <X size={18} />
              </button>
            </div>

            {loadingDetail ? (
              <div className="p-12 text-center text-slate-400 flex flex-col items-center gap-2">
                <Loader2 size={28} className="animate-spin text-blue-600" />
                <span className="text-xs">Загрузка карточки пользователя...</span>
              </div>
            ) : userDetail ? (
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {/* User Header Summary */}
                <div className="p-3 bg-slate-50 border border-slate-100 rounded-xl space-y-2">
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="font-bold text-sm text-slate-900">{userDetail.profile.first_name}</div>
                      {userDetail.profile.username && (
                        <a
                          href={`https://t.me/${userDetail.profile.username}`}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs text-blue-600 font-mono hover:underline"
                        >
                          @{userDetail.profile.username}
                        </a>
                      )}
                    </div>
                    {getSubBadge(userDetail.profile.subscription_status, userDetail.is_banned)}
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs text-slate-600 pt-1 border-t border-slate-200/60">
                    <div><span className="text-slate-400">Профессия:</span> {userDetail.profile.profession_id}</div>
                    <div><span className="text-slate-400">Опыт:</span> {userDetail.profile.experience_years} год(а)</div>
                    <div><span className="text-slate-400">Локация:</span> {userDetail.profile.location}</div>
                    <div>
                      <span className="text-slate-400">Подписка до:</span>{' '}
                      {userDetail.profile.subscription_until
                        ? new Date(userDetail.profile.subscription_until).toLocaleDateString('ru-RU')
                        : 'Нет'}
                    </div>
                  </div>
                </div>

                {/* Internal Tabs inside Modal */}
                <div className="flex border-b border-slate-200">
                  <button
                    onClick={() => setModalTab('profile')}
                    className={`px-3 py-2 text-xs font-medium border-b-2 transition-all ${
                      modalTab === 'profile' ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500'
                    }`}
                  >
                    О себе & Стек
                  </button>
                  <button
                    onClick={() => setModalTab('channels')}
                    className={`px-3 py-2 text-xs font-medium border-b-2 transition-all ${
                      modalTab === 'channels' ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500'
                    }`}
                  >
                    Чаты ({userDetail.connected_channels.length})
                  </button>
                  <button
                    onClick={() => setModalTab('sub')}
                    className={`px-3 py-2 text-xs font-medium border-b-2 transition-all ${
                      modalTab === 'sub' ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500'
                    }`}
                  >
                    Управление подпиской
                  </button>
                  <button
                    onClick={() => setModalTab('ban')}
                    className={`px-3 py-2 text-xs font-medium border-b-2 transition-all ${
                      modalTab === 'ban' ? 'border-red-600 text-red-600' : 'border-transparent text-slate-500'
                    }`}
                  >
                    Блокировка
                  </button>
                </div>

                {/* Modal Tab Content */}
                {modalTab === 'profile' && (
                  <div className="space-y-3 text-xs">
                    <div>
                      <div className="font-semibold text-slate-700 mb-1">О себе (Bio Summary):</div>
                      <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-slate-800 leading-relaxed whitespace-pre-wrap">
                        {userDetail.bio_summary || 'Пользователь пока не добавил описание о себе.'}
                      </div>
                    </div>

                    <div>
                      <div className="font-semibold text-slate-700 mb-1">Стек технологий:</div>
                      <div className="flex flex-wrap gap-1">
                        {userDetail.software_stack.length > 0 ? (
                          userDetail.software_stack.map((s, idx) => (
                            <span key={idx} className="px-2 py-1 bg-blue-50 text-blue-700 border border-blue-100 rounded-md font-mono text-[11px]">
                              {s}
                            </span>
                          ))
                        ) : (
                          <span className="text-slate-400">Стек не указан</span>
                        )}
                      </div>
                    </div>

                    <div>
                      <div className="font-semibold text-slate-700 mb-1">Стоп-слова:</div>
                      <div className="flex flex-wrap gap-1">
                        {userDetail.stop_words.length > 0 ? (
                          userDetail.stop_words.map((w, idx) => (
                            <span key={idx} className="px-2 py-1 bg-rose-50 text-rose-700 border border-rose-100 rounded-md text-[11px]">
                              {w}
                            </span>
                          ))
                        ) : (
                          <span className="text-slate-400">Стоп-слова не заданы</span>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                {modalTab === 'channels' && (
                  <div className="space-y-2 text-xs">
                    <div className="font-semibold text-slate-700">Отслеживаемые каналы и чаты:</div>
                    {userDetail.connected_channels.length === 0 ? (
                      <div className="p-4 bg-slate-50 text-center text-slate-400 rounded-lg">
                        Нет подключенных чатов
                      </div>
                    ) : (
                      <div className="space-y-1.5 max-h-48 overflow-y-auto">
                        {userDetail.connected_channels.map((c) => (
                          <div key={c.channel_id} className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg flex items-center justify-between">
                            <div>
                              <div className="font-medium text-slate-900">{c.title}</div>
                              <div className="text-[10px] text-blue-600 font-mono">@{c.username}</div>
                            </div>
                            <span className={`text-[10px] px-2 py-0.5 rounded ${c.is_enabled ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-600'}`}>
                              {c.is_enabled ? 'Включен' : 'Отключен'}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {modalTab === 'sub' && (
                  <div className="space-y-4 text-xs">
                    <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-blue-800 space-y-1">
                      <div className="font-semibold">Текущий статус подписки:</div>
                      <div>Статус: <b>{userDetail.profile.subscription_status}</b></div>
                      <div>Продлена до: <b>{userDetail.profile.subscription_until ? new Date(userDetail.profile.subscription_until).toLocaleString('ru-RU') : 'Не задана'}</b></div>
                    </div>

                    <div className="space-y-2">
                      <div className="font-semibold text-slate-700">Быстрое продление доступа:</div>
                      <div className="grid grid-cols-3 gap-2">
                        <button
                          disabled={updatingSub}
                          onClick={() => handleUpdateSubscription('add_days', 7)}
                          className="py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-medium shadow-sm transition-all flex items-center justify-center gap-1 disabled:opacity-50"
                        >
                          <Plus size={14} /> +7 Дней
                        </button>
                        <button
                          disabled={updatingSub}
                          onClick={() => handleUpdateSubscription('add_days', 30)}
                          className="py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-medium shadow-sm transition-all flex items-center justify-center gap-1 disabled:opacity-50"
                        >
                          <Plus size={14} /> +30 Дней
                        </button>
                        <button
                          disabled={updatingSub}
                          onClick={() => handleUpdateSubscription('add_days', 365)}
                          className="py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-medium shadow-sm transition-all flex items-center justify-center gap-1 disabled:opacity-50"
                        >
                          <Plus size={14} /> +1 Год
                        </button>
                      </div>
                    </div>

                    <div className="pt-2 border-t border-slate-200">
                      <button
                        disabled={updatingSub}
                        onClick={() => handleUpdateSubscription('revoke')}
                        className="w-full py-2.5 bg-amber-600 hover:bg-amber-700 text-white rounded-lg font-medium shadow-sm transition-all flex items-center justify-center gap-2 disabled:opacity-50"
                      >
                        <XCircle size={15} /> Аннулировать подписку (Сделать истекшей)
                      </button>
                    </div>
                  </div>
                )}

                {modalTab === 'ban' && (
                  <div className="space-y-4 text-xs">
                    <div className="space-y-1.5">
                      <label className="font-semibold text-slate-700">Причина блокировки:</label>
                      <input
                        type="text"
                        placeholder="Например: Спам, нарушение правил, заявка пользователя..."
                        value={banReason}
                        onChange={(e) => setBanReason(e.target.value)}
                        className="w-full bg-slate-50 border border-slate-200 p-2.5 rounded-lg text-xs focus:outline-none focus:border-red-500"
                      />
                    </div>

                    {userDetail.is_banned ? (
                      <button
                        disabled={updatingBan}
                        onClick={() => handleToggleBan(false)}
                        className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-semibold transition-all flex items-center justify-center gap-2 disabled:opacity-50"
                      >
                        <UserCheck size={16} /> Разблокировать пользователя
                      </button>
                    ) : (
                      <button
                        disabled={updatingBan}
                        onClick={() => handleToggleBan(true)}
                        className="w-full py-2.5 bg-red-600 hover:bg-red-700 text-white rounded-lg font-semibold transition-all flex items-center justify-center gap-2 disabled:opacity-50"
                      >
                        <Ban size={16} /> Заблокировать пользователя
                      </button>
                    )}
                  </div>
                )}
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
};
