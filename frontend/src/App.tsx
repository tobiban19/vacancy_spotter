import { useEffect, useState, useRef } from 'react';
import {
  User,
  Briefcase,
  Radio,
  CreditCard,
  Plus,
  Trash2,
  X,
  ShieldAlert,
  Loader2,
  ExternalLink,
  Copy,
  Check,
  Send,
  CheckCircle2,
  Upload,
  ShieldCheck,
  Zap,
  MessageCircleQuestion,
  ShieldCheck as AdminShieldIcon,
} from 'lucide-react';
import { api, UserProfile, PortfolioItem, Channel } from './api';
import { AdminPanel } from './AdminPanel';

interface TelegramUser {
  id?: number;
  first_name?: string;
  last_name?: string;
  username?: string;
}

const DEFAULT_PROFESSIONS = [
  { id: 'video_editor', title_ru: 'Видеомонтаж / Reelsmaker', icon_emoji: '🎬' },
  { id: 'motion_designer', title_ru: 'Motion Designer', icon_emoji: '🎨' },
  { id: 'web_designer', title_ru: 'Веб-дизайнер / UI/UX', icon_emoji: '🖥️' },
  { id: 'copywriter', title_ru: 'Копирайтер', icon_emoji: '✍️' },
  { id: '3d_artist', title_ru: '3D Artist', icon_emoji: '🧊' },
  { id: 'smm', title_ru: 'SMM-специалист', icon_emoji: '📱' },
];

// Telegram Haptic Feedback helper
const triggerHaptic = (style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft' = 'light') => {
  try {
    (window as any).Telegram?.WebApp?.HapticFeedback?.impactOccurred(style);
  } catch (e) {
    // ignore
  }
};

export function App() {
  const [activeTab, setActiveTab] = useState<'profile' | 'portfolio' | 'channels' | 'subscription' | 'admin'>('profile');
  const [tgUser, setTgUser] = useState<TelegramUser | null>(null);
  const [isAdmin, setIsAdmin] = useState<boolean>(false);

  // API State
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [portfolio, setPortfolio] = useState<PortfolioItem[]>([]);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [savingProfile, setSavingProfile] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Profile Edit State
  const [professionId, setProfessionId] = useState<string>('video_editor');
  const [stopWords, setStopWords] = useState<string[]>([]);
  const [newStopWord, setNewStopWord] = useState<string>('');
  const [bioSummary, setBioSummary] = useState<string>('');

  // PDF Upload State
  const [uploadingPdf, setUploadingPdf] = useState<boolean>(false);
  const pdfInputRef = useRef<HTMLInputElement>(null);

  // Instructions Modal State
  const [showInstructions, setShowInstructions] = useState<boolean>(false);

  // Portfolio Form State
  const [showAddPortfolio, setShowAddPortfolio] = useState<boolean>(false);
  const [portTitle, setPortTitle] = useState<string>('');
  const [portUrl, setPortUrl] = useState<string>('');
  const [portDesc, setPortDesc] = useState<string>('');
  const [addingPortfolio, setAddingPortfolio] = useState<boolean>(false);

  // Custom Channel Input State
  const [customChannelInput, setCustomChannelInput] = useState<string>('');
  const [addingChannel, setAddingChannel] = useState<boolean>(false);

  // Subscription State
  const [selectedPlan, setSelectedPlan] = useState<'week' | 'month'>('month');
  const [copiedCard, setCopiedCard] = useState<boolean>(false);
  const [submittingCardRequest, setSubmittingCardRequest] = useState<boolean>(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Onboarding Wizard State
  const [showOnboarding, setShowOnboarding] = useState<boolean>(false);
  const [onboardingStep, setOnboardingStep] = useState<number>(1);
  const [experienceYears, setExperienceYears] = useState<number>(1);

  const CARD_NUMBER = '2203 3101 8911 3452';

  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    setToast({ message, type });
    setTimeout(() => {
      setToast(null);
    }, 4000);
  };

  const handleTabChange = (tab: 'profile' | 'portfolio' | 'channels' | 'subscription' | 'admin') => {
    triggerHaptic('light');
    setActiveTab(tab);
  };

  const handleCopyCard = async () => {
    triggerHaptic('light');
    try {
      await navigator.clipboard.writeText(CARD_NUMBER.replace(/\s/g, ''));
      setCopiedCard(true);
      setTimeout(() => setCopiedCard(false), 2000);
    } catch (err) {
      console.error('Failed to copy card:', err);
    }
  };

  // Receipt Attachment State
  const [receiptInfo, setReceiptInfo] = useState('');
  const [receiptFile, setReceiptFile] = useState<{ name: string; b64: string } | null>(null);
  const receiptFileInputRef = useRef<HTMLInputElement>(null);

  const handleReceiptFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 10 * 1024 * 1024) {
      showToast('Размер файла чека не должен превышать 10 МБ', 'error');
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      const b64 = reader.result as string;
      setReceiptFile({ name: file.name, b64 });
      showToast(`📎 Чек «${file.name}» прикреплён!`, 'success');
    };
    reader.readAsDataURL(file);
  };

  const handleRequestCard = async () => {
    triggerHaptic('medium');
    if (!receiptInfo.trim() && !receiptFile) {
      showToast('Прикрепите файл чека (PDF или изображение) или укажите данные перевода!', 'error');
      return;
    }
    setSubmittingCardRequest(true);
    try {
      await api.requestCardSubscription(
        selectedPlan,
        receiptInfo.trim(),
        receiptFile?.b64,
        receiptFile?.name,
      );
      showToast('Отправили чек администратору. Проверим перевод и активируем подписку в течение 15 минут.', 'success');
      setReceiptInfo('');
      setReceiptFile(null);
    } catch (err: any) {
      console.error('Failed to request card subscription:', err);
      showToast('Ошибка при отправке запроса. Попробуйте еще раз.', 'error');
    } finally {
      setSubmittingCardRequest(false);
    }
  };

  const handlePdfUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      showToast('Выберите файл формата PDF', 'error');
      return;
    }
    setUploadingPdf(true);
    triggerHaptic('medium');
    try {
      const res = await api.parseResumePdf(file);
      if (res.extracted_text) {
        setBioSummary((prev) => (prev ? `${prev}\n\n${res.extracted_text}` : res.extracted_text));
        showToast('Прочитали PDF. Добавили навыки и опыт в профиль.', 'success');
      }
    } catch (err: any) {
      console.error('PDF upload error:', err);
      showToast(err.message || 'Не удалось прочитать PDF файл', 'error');
    } finally {
      setUploadingPdf(false);
      if (pdfInputRef.current) pdfInputRef.current.value = '';
    }
  };

  const getSubscriptionInfo = () => {
    if (!profile) return { title: 'Загрузка...', status: 'demo', daysLeft: 0, formattedUntil: '' };
    const isDemo = profile.subscription_status !== 'active';
    const targetDateStr = isDemo ? profile.demo_until : (profile.subscription_until || profile.demo_until);

    if (!targetDateStr) {
      return { title: 'Демо Доступ (2 дня)', status: 'demo', daysLeft: 2, formattedUntil: 'Активен' };
    }

    const targetDate = new Date(targetDateStr);
    const now = new Date();
    const diffMs = targetDate.getTime() - now.getTime();
    const daysLeft = Math.max(0, Math.ceil(diffMs / (1000 * 60 * 60 * 24)));

    const dateFormatted = targetDate.toLocaleDateString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });

    return {
      title: isDemo ? 'Демо Доступ (2 дня)' : 'Подписка',
      status: isDemo ? 'demo' : 'active',
      daysLeft,
      formattedUntil: dateFormatted,
    };
  };

  // Load Data on Mount
  useEffect(() => {
    const tg = (window as any).Telegram?.WebApp;
    if (tg) {
      tg.ready();
      tg.expand();
      setTgUser(tg.initDataUnsafe?.user || { first_name: 'Фрилансер' });
    } else {
      setTgUser({ first_name: 'Демо Пользователь' });
    }

    loadInitialData();
  }, []);

  const loadInitialData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [profileData, portfolioData, channelsData, adminRes] = await Promise.all([
        api.getProfile().catch(() => null),
        api.getPortfolio().catch(() => []),
        api.getChannels().catch(() => []),
        api.checkAdmin().catch(() => ({ is_admin: false, user_id: 0 })),
      ]);

      if (profileData) {
        setProfile(profileData);
        setProfessionId(profileData.profession_id || 'video_editor');
        setStopWords(profileData.stop_words || []);
        setBioSummary(profileData.bio_summary || '');
      }

      setPortfolio(portfolioData || []);
      setChannels(channelsData || []);
      setIsAdmin(Boolean(adminRes?.is_admin));
    } catch (err: any) {
      console.error('Failed to load initial data:', err);
      setError('Не удалось загрузить данные с сервера');
    } finally {
      setLoading(false);
    }
  };

  // --- Profile Handlers ---
  const handleProfessionChange = async (newId: string) => {
    triggerHaptic('light');
    setProfessionId(newId);
    try {
      const updated = await api.updateProfile({ profession_id: newId });
      setProfile(updated);
      const newChannels = await api.getChannels();
      setChannels(newChannels);
    } catch (err) {
      console.error('Failed to update profession:', err);
    }
  };

  const handleAddStopWord = async () => {
    triggerHaptic('light');
    const trimmed = newStopWord.trim();
    if (!trimmed || stopWords.includes(trimmed)) return;

    const updatedWords = [...stopWords, trimmed];
    setStopWords(updatedWords);
    setNewStopWord('');
    try {
      const updated = await api.updateProfile({ stop_words: updatedWords });
      setProfile(updated);
    } catch (err) {
      console.error('Failed to update stop words:', err);
    }
  };

  const handleRemoveStopWord = async (wordToRemove: string) => {
    triggerHaptic('light');
    const updatedWords = stopWords.filter((w) => w !== wordToRemove);
    setStopWords(updatedWords);
    try {
      const updated = await api.updateProfile({ stop_words: updatedWords });
      setProfile(updated);
    } catch (err) {
      console.error('Failed to remove stop word:', err);
    }
  };

  const handleSaveProfile = async () => {
    triggerHaptic('medium');
    setSavingProfile(true);
    try {
      const updated = await api.updateProfile({
        profession_id: professionId,
        stop_words: stopWords,
        bio_summary: bioSummary,
      });
      setProfile(updated);
      showToast('Профиль успешно сохранен', 'success');
    } catch (err) {
      console.error('Failed to save profile:', err);
      showToast('Не удалось сохранить профиль', 'error');
    } finally {
      setSavingProfile(false);
    }
  };

  // --- Portfolio Handlers ---
  const handleAddPortfolio = async (e: React.FormEvent) => {
    e.preventDefault();
    triggerHaptic('medium');
    if (!portTitle.trim() || !portUrl.trim()) return;

    setAddingPortfolio(true);
    try {
      const newItem = await api.addPortfolioItem({
        title: portTitle.trim(),
        url: portUrl.trim(),
        description: portDesc.trim(),
        category: 'general',
        orientation: 'horizontal',
      });
      setPortfolio((prev) => [newItem, ...prev]);
      setPortTitle('');
      setPortUrl('');
      setPortDesc('');
      setShowAddPortfolio(false);
      showToast('Кейс добавлен в портфолио', 'success');
    } catch (err) {
      console.error('Failed to add portfolio item:', err);
      showToast('Ошибка при добавлении кейса', 'error');
    } finally {
      setAddingPortfolio(false);
    }
  };

  const handleDeletePortfolio = async (id: number) => {
    triggerHaptic('light');
    try {
      await api.deletePortfolioItem(id);
      setPortfolio((prev) => prev.filter((item) => item.id !== id));
      showToast('Кейс удален', 'success');
    } catch (err) {
      console.error('Failed to delete portfolio item:', err);
    }
  };

  // --- Channel Handlers ---
  const handleToggleChannel = async (channelId: number, currentStatus: boolean) => {
    triggerHaptic('light');
    const nextStatus = !currentStatus;
    setChannels((prev) =>
      prev.map((ch) => (ch.id === channelId ? { ...ch, is_enabled: nextStatus } : ch))
    );

    try {
      await api.toggleChannel(channelId, nextStatus);
    } catch (err) {
      console.error('Failed to toggle channel:', err);
      setChannels((prev) =>
        prev.map((ch) => (ch.id === channelId ? { ...ch, is_enabled: currentStatus } : ch))
      );
    }
  };

  const handleAddCustomChannel = async (e: React.FormEvent) => {
    e.preventDefault();
    triggerHaptic('light');
    const input = customChannelInput.trim();
    if (!input) return;

    setAddingChannel(true);
    try {
      const newCh = await api.addCustomChannel(input);
      setChannels((prev) => [...prev, newCh]);
      setCustomChannelInput('');
      showToast('Канал успешно добавлен', 'success');
    } catch (err) {
      console.error('Failed to add custom channel:', err);
      showToast('Не удалось добавить канал', 'error');
    } finally {
      setAddingChannel(false);
    }
  };

  return (
    <div className="flex flex-col min-h-screen max-w-md mx-auto pb-24 px-4 pt-4 font-body selection:bg-[#005BB3] selection:text-white bg-slate-50 text-slate-900">
      {/* Toast Notification */}
      {toast && (
        <div className="fixed top-4 left-4 right-4 max-w-md mx-auto z-50 animate-fadeIn">
          <div
            className={`p-3.5 rounded-xl border shadow-lg flex items-start gap-3 backdrop-blur-md ${
              toast.type === 'success'
                ? 'bg-emerald-50 border-[#029456]/40 text-[#029456] shadow-emerald-500/5'
                : 'bg-rose-50 border-[#D8226C]/40 text-[#D8226C] shadow-rose-500/5'
            }`}
          >
            <CheckCircle2 size={18} className="text-[#029456] shrink-0 mt-0.5" />
            <div className="flex-1 text-xs font-medium leading-relaxed font-body">{toast.message}</div>
            <button
              type="button"
              onClick={() => {
                triggerHaptic('light');
                setToast(null);
              }}
              className="text-slate-400 hover:text-slate-700 transition-colors p-0.5"
            >
              <X size={14} />
            </button>
          </div>
        </div>
      )}

      {/* ONBOARDING MODAL WIZARD */}
      {showOnboarding && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl p-5 max-w-sm w-full space-y-4 shadow-xl animate-fadeIn border border-[#B2DAE4]/50">
            {/* Header */}
            <div className="text-center space-y-1">
              <span className="text-[10px] font-bold tracking-wider px-2.5 py-0.5 rounded-full bg-[#B2DAE4]/30 text-[#005BB3] border border-[#005BB3]/20 uppercase font-body">
                Настройка профиля (Шаг {onboardingStep} из 3)
              </span>
              <h3 className="font-heading text-base font-bold text-slate-900 pt-1">
                {onboardingStep === 1 && 'Выберите профессию'}
                {onboardingStep === 2 && 'Опыт работы и фильтры'}
                {onboardingStep === 3 && 'Первый проект в портфолио'}
              </h3>
              <p className="font-body text-xs text-slate-500">
                {onboardingStep === 1 && 'Бот ищет вакансии по вашей специальности.'}
                {onboardingStep === 2 && 'Укажите стаж и слова для фильтрации.'}
                {onboardingStep === 3 && 'Нейросеть будет прикладывать этот проект к отклику.'}
              </p>
            </div>

            {/* Step 1: Professions */}
            {onboardingStep === 1 && (
              <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                {DEFAULT_PROFESSIONS.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => {
                      triggerHaptic('light');
                      setProfessionId(p.id);
                    }}
                    className={`w-full p-2.5 rounded-xl border text-left flex items-center justify-between text-xs font-body transition-all hover:-translate-y-0.5 ${
                      professionId === p.id
                        ? 'bg-[#005BB3]/10 border-[#005BB3] text-[#005BB3] font-semibold shadow-sm'
                        : 'bg-slate-50 hover:bg-slate-100 border-slate-200 text-slate-700'
                    }`}
                  >
                    <span>{p.icon_emoji} {p.title_ru}</span>
                    {professionId === p.id && <Check size={16} className="text-[#005BB3]" />}
                  </button>
                ))}
              </div>
            )}

            {/* Step 2: Experience & Stop-words */}
            {onboardingStep === 2 && (
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium font-body text-slate-700 mb-1">Стаж работы (лет):</label>
                  <input
                    type="number"
                    min="0"
                    max="20"
                    value={experienceYears}
                    onChange={(e) => setExperienceYears(parseInt(e.target.value) || 0)}
                    className="w-full bg-slate-50 text-slate-900 p-2.5 rounded-lg border border-slate-200 text-xs font-body focus:outline-none focus:border-[#005BB3] focus:bg-white"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium font-body text-slate-700 mb-1">Стоп-слова (пропускать вакансии со словами):</label>
                  <input
                    type="text"
                    value={newStopWord}
                    onChange={(e) => setNewStopWord(e.target.value)}
                    placeholder="бартер, бесплатно, стажёр"
                    className="w-full bg-slate-50 text-slate-900 p-2.5 rounded-lg border border-slate-200 text-xs font-body focus:outline-none focus:border-[#005BB3] focus:bg-white"
                  />
                  <p className="text-[10px] text-slate-500 mt-1 font-body">Указывайте слова через запятую</p>
                </div>
              </div>
            )}

            {/* Step 3: First Portfolio Item */}
            {onboardingStep === 3 && (
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium font-body text-slate-700 mb-1">Название проекта:</label>
                  <input
                    type="text"
                    value={portTitle}
                    onChange={(e) => setPortTitle(e.target.value)}
                    placeholder="Showreel 2026 или Проморолик"
                    className="w-full bg-slate-50 text-slate-900 p-2.5 rounded-lg border border-slate-200 text-xs font-body focus:outline-none focus:border-[#005BB3] focus:bg-white"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium font-body text-slate-700 mb-1">Ссылка на проект (YouTube, Behance, Диск):</label>
                  <input
                    type="url"
                    value={portUrl}
                    onChange={(e) => setPortUrl(e.target.value)}
                    placeholder="https://..."
                    className="w-full bg-slate-50 text-slate-900 p-2.5 rounded-lg border border-slate-200 text-xs font-body focus:outline-none focus:border-[#005BB3] focus:bg-white"
                  />
                </div>
              </div>
            )}

            {/* Step Navigation Buttons */}
            <div className="flex items-center gap-2 pt-2">
              {onboardingStep > 1 && (
                <button
                  type="button"
                  onClick={() => {
                    triggerHaptic('light');
                    setOnboardingStep((s) => s - 1);
                  }}
                  className="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-700 py-2.5 rounded-xl text-xs font-semibold font-body transition-all hover:-translate-y-0.5 active:translate-y-0"
                >
                  Назад
                </button>
              )}
              <button
                type="button"
                onClick={async () => {
                  triggerHaptic('medium');
                  if (onboardingStep < 3) {
                    setOnboardingStep((s) => s + 1);
                  } else {
                    try {
                      const words = newStopWord ? newStopWord.split(',').map(s => s.trim()).filter(Boolean) : stopWords;
                      await api.updateProfile({
                        profession_id: professionId,
                        experience_years: experienceYears,
                        stop_words: words,
                      });
                      if (portTitle.trim() && portUrl.trim()) {
                        await api.addPortfolioItem({
                          title: portTitle.trim(),
                          url: portUrl.trim(),
                          description: 'Проект из мастера настройки',
                          category: 'general',
                        });
                      }
                      localStorage.setItem('spotter_onboarding_done', 'true');
                      setShowOnboarding(false);
                      showToast('Настроили профиль. Включили PRO-доступ на 2 дня.', 'success');
                      loadInitialData();
                    } catch (err) {
                      console.error('Onboarding save error:', err);
                      setShowOnboarding(false);
                    }
                  }
                }}
                className="flex-1 bg-gradient-to-r from-[#005BB3] to-[#D8226C] hover:from-[#004b94] hover:to-[#b81b5b] text-white py-2.5 rounded-xl text-xs font-bold font-body transition-all hover:-translate-y-0.5 active:translate-y-0 shadow-md shadow-[#005BB3]/20"
              >
                {onboardingStep === 3 ? 'Сохранить и начать поиск' : 'Далее →'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* INSTRUCTION MODAL */}
      {showInstructions && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl p-5 max-w-sm w-full space-y-4 shadow-xl animate-fadeIn border border-[#B2DAE4]/60 max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-100 pb-2">
              <h3 className="font-heading text-base font-bold text-slate-900 flex items-center gap-2">
                Как работает Vacancy Spotter
              </h3>
              <button
                type="button"
                onClick={() => setShowInstructions(false)}
                className="text-slate-400 hover:text-slate-700 p-1"
              >
                <X size={18} />
              </button>
            </div>

            <div className="space-y-3 font-body text-xs text-slate-700">
              <div className="p-3 bg-[#005BB3]/5 border border-[#005BB3]/20 rounded-xl space-y-1">
                <div className="font-bold text-[#005BB3] flex items-center gap-1.5 text-sm">
                  1. Настройка профиля и стоп-слов
                </div>
                <p className="text-slate-600">
                  Выберите вашу специализацию и укажите стоп-слова. Бот автоматически пропустит вакансии, где есть эти слова.
                </p>
              </div>

              <div className="p-3 bg-[#D8226C]/5 border border-[#D8226C]/20 rounded-xl space-y-1">
                <div className="font-bold text-[#D8226C] flex items-center gap-1.5 text-sm">
                  2. Загрузка резюме в PDF
                </div>
                <p className="text-slate-600">
                  Нажмите <b>«Извлечь из PDF»</b> в профиле — бот сам прочитает ваш опыт и учтёт его при подготовке откликов.
                </p>
              </div>

              <div className="p-3 bg-[#F86A38]/5 border border-[#F86A38]/20 rounded-xl space-y-1">
                <div className="font-bold text-[#e04e1b] flex items-center gap-1.5 text-sm">
                  3. Проекты в портфолио
                </div>
                <p className="text-slate-600">
                  Прикрепите ссылки на проекты (YouTube, Behance, Диск). Бот подберёт под каждую вакансию наиболее подходящие примеры.
                </p>
              </div>

              <div className="p-3 bg-[#029456]/5 border border-[#029456]/20 rounded-xl space-y-1">
                <div className="font-bold text-[#029456] flex items-center gap-1.5 text-sm">
                  4. Проверка и отправка откликов
                </div>
                <p className="text-slate-600">
                  Когда появится подходящая вакансия, бот пришлёт готовый отклик. Вам останется нажать <b>«Отправить отклик»</b>.
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setShowInstructions(false)}
              className="w-full bg-gradient-to-r from-[#005BB3] to-[#D8226C] hover:from-[#004b94] hover:to-[#b81b5b] text-white py-2.5 rounded-xl font-bold text-xs shadow-md"
            >
              Понятно
            </button>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#B2DAE4]/50 pb-3 mb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-heading text-xl font-bold text-[#D8226C]">
              Vacancy Spotter
            </h1>
          </div>
          <p className="font-body text-xs text-slate-500">
            Привет, {tgUser?.first_name || profile?.first_name || 'Пользователь'} 👋
          </p>
        </div>
        <span
          className={`font-body text-xs px-2.5 py-1 rounded-full font-medium ${
            profile?.subscription_status === 'active'
              ? 'figma-emerald-badge'
              : 'figma-coral-badge'
          }`}
        >
          {profile?.subscription_status === 'active' ? 'Подписка активна' : 'Демо Тариф'}
        </span>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="mb-4 p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl flex items-center gap-2 text-rose-400 text-xs font-body">
          <ShieldAlert size={16} />
          <span>{error}</span>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 space-y-4">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 text-slate-400 space-y-3 font-body">
            <Loader2 className="animate-spin text-blue-400" size={32} />
            <p className="text-sm font-medium">Загрузка данных...</p>
          </div>
        ) : (
          <>
            {/* PROFILE TAB */}
            {activeTab === 'profile' && (
              <div className="space-y-4 animate-fadeIn">
                <div className="flex items-center justify-between">
                  <h2 className="font-heading text-lg font-semibold flex items-center gap-2 text-slate-900">
                    <User size={20} className="text-[#005BB3]" /> Профиль & Профессия
                  </h2>
                  <button
                    type="button"
                    onClick={() => {
                      triggerHaptic('light');
                      setOnboardingStep(1);
                      setShowOnboarding(true);
                    }}
                    className="font-body text-xs bg-[#B2DAE4]/30 hover:bg-[#B2DAE4]/50 text-[#005BB3] border border-[#005BB3]/20 px-2.5 py-1 rounded-lg transition-all hover:-translate-y-0.5 active:translate-y-0 font-medium flex items-center gap-1"
                  >
                    🪄 Обучение
                  </button>
                </div>

                {/* SUBSCRIPTION MANAGEMENT CARD */}
                {(() => {
                  const subInfo = getSubscriptionInfo();
                  return (
                    <div className="glass-card p-4 rounded-xl space-y-3 border border-[#B2DAE4]/60 shadow-sm font-body">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2.5">
                          <div className={`p-2 rounded-xl ${subInfo.status === 'active' ? 'bg-emerald-100 text-[#029456]' : 'bg-amber-100 text-[#F86A38]'}`}>
                            <ShieldCheck size={20} />
                          </div>
                          <div>
                            <h4 className="font-heading text-sm font-bold text-slate-900">{subInfo.title}</h4>
                            <p className="text-xs text-slate-500">
                              До {subInfo.formattedUntil} • <span className="font-medium text-slate-700">{subInfo.daysLeft} дн. осталось</span>
                            </p>
                          </div>
                        </div>
                        <span className={`text-[11px] font-semibold px-2.5 py-1 rounded-full ${subInfo.status === 'active' ? 'figma-emerald-badge' : 'figma-coral-badge'}`}>
                          {subInfo.status === 'active' ? 'Активен' : 'Демо'}
                        </span>
                      </div>

                      <div className="flex gap-2 pt-1">
                        <button
                          type="button"
                          onClick={() => {
                            triggerHaptic('medium');
                            setActiveTab('subscription');
                          }}
                          className="flex-1 bg-[#D8226C] hover:bg-[#b81b5b] text-white text-xs py-2 rounded-lg font-bold shadow-sm flex items-center justify-center gap-1.5 transition-all hover:-translate-y-0.5 active:translate-y-0"
                        >
                          <Zap size={14} /> Управление & Продлить
                        </button>

                        <a
                          href="https://t.me/p_timofeev"
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={() => triggerHaptic('light')}
                          className="bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300 text-xs px-3 py-2 rounded-lg font-medium flex items-center gap-1 transition-all hover:-translate-y-0.5"
                        >
                          <MessageCircleQuestion size={14} /> Поддержка
                        </a>
                      </div>
                    </div>
                  );
                })()}

                <div className="glass-card glass-card-hover p-4 rounded-xl space-y-4 shadow-sm">
                  <div>
                    <label className="block font-body text-xs font-medium text-slate-700 mb-1.5">
                      Основная специализация
                    </label>
                    <select
                      value={professionId}
                      onChange={(e) => handleProfessionChange(e.target.value)}
                      className="w-full bg-slate-50 text-slate-900 p-2.5 rounded-lg border border-slate-200 focus:outline-none focus:border-[#005BB3] focus:bg-white text-sm font-body"
                    >
                      {DEFAULT_PROFESSIONS.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.icon_emoji} {p.title_ru}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block font-body text-xs font-medium text-slate-700 mb-1.5">
                      Стоп-слова (исключать вакансии с этими словами)
                    </label>
                    <div className="flex gap-2 mb-2">
                      <input
                        type="text"
                        value={newStopWord}
                        onChange={(e) => setNewStopWord(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddStopWord())}
                        placeholder="Например: стажер, бартер, бесплатно"
                        className="flex-1 bg-slate-50 text-slate-900 px-3 py-2 rounded-lg border border-slate-200 focus:outline-none focus:border-[#005BB3] focus:bg-white text-xs font-body"
                      />
                      <button
                        type="button"
                        onClick={handleAddStopWord}
                        className="font-body bg-[#005BB3] hover:bg-[#004b94] hover:-translate-y-0.5 active:translate-y-0 text-white text-xs px-3 py-2 rounded-lg transition-all font-medium flex items-center gap-1 shadow-sm"
                      >
                        <Plus size={14} /> Добавить
                      </button>
                    </div>
                    {stopWords.length > 0 ? (
                      <div className="flex flex-wrap gap-1.5 pt-1">
                        {stopWords.map((word) => (
                          <span
                            key={word}
                            className="inline-flex items-center gap-1 bg-[#B2DAE4]/30 text-[#005BB3] border border-[#B2DAE4] px-2.5 py-1 rounded-md text-xs font-body font-medium"
                          >
                            {word}
                            <button
                              type="button"
                              onClick={() => handleRemoveStopWord(word)}
                              className="text-[#005BB3]/70 hover:text-[#D8226C] transition-colors ml-0.5"
                            >
                              <X size={12} />
                            </button>
                          </span>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-slate-500 italic font-body">Стоп-слова не заданы</p>
                    )}
                  </div>

                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <label className="font-body text-xs font-medium text-slate-700">
                        Опыт и навыки (для ИИ откликов)
                      </label>
                      <input
                        type="file"
                        accept=".pdf"
                        ref={pdfInputRef}
                        onChange={handlePdfUpload}
                        className="hidden"
                      />
                      <button
                        type="button"
                        disabled={uploadingPdf}
                        onClick={() => {
                          triggerHaptic('light');
                          pdfInputRef.current?.click();
                        }}
                        className="text-xs bg-[#005BB3]/10 hover:bg-[#005BB3]/20 text-[#005BB3] border border-[#005BB3]/30 px-2.5 py-1 rounded-md transition-all font-medium flex items-center gap-1"
                      >
                        {uploadingPdf ? (
                          <>
                            <Loader2 className="animate-spin" size={12} />
                            <span>Чтение PDF...</span>
                          </>
                        ) : (
                          <>
                            <Upload size={12} />
                            <span>📄 Извлечь из PDF</span>
                          </>
                        )}
                      </button>
                    </div>
                    <textarea
                      rows={4}
                      value={bioSummary}
                      onChange={(e) => setBioSummary(e.target.value)}
                      placeholder="Опишите ваш опыт, ключевые навыки и проекты или загрузите резюме в PDF..."
                      className="w-full bg-slate-50 text-slate-900 p-2.5 rounded-lg border border-slate-200 focus:outline-none focus:border-[#005BB3] focus:bg-white text-xs font-body resize-none"
                    />
                  </div>

                  <button
                    onClick={handleSaveProfile}
                    disabled={savingProfile}
                    className="w-full font-body bg-[#D8226C] hover:bg-[#b81b5b] hover:-translate-y-0.5 active:translate-y-0 disabled:opacity-50 text-white font-medium py-2.5 rounded-lg transition-all text-sm shadow-md flex items-center justify-center gap-2"
                  >
                    {savingProfile ? (
                      <>
                        <Loader2 className="animate-spin" size={16} /> Сохранение...
                      </>
                    ) : (
                      'Сохранить изменения'
                    )}
                  </button>
                </div>
              </div>
            )}

            {/* PORTFOLIO TAB */}
            {activeTab === 'portfolio' && (
              <div className="space-y-4 animate-fadeIn">
                <div className="flex items-center justify-between">
                  <h2 className="font-heading text-lg font-semibold flex items-center gap-2 text-slate-900">
                    <Briefcase size={20} className="text-[#005BB3]" /> Портфолио и проекты
                  </h2>
                  <button
                    onClick={() => {
                      triggerHaptic('light');
                      setShowAddPortfolio(!showAddPortfolio);
                    }}
                    className="font-body bg-[#005BB3] hover:bg-[#004b94] hover:-translate-y-0.5 active:translate-y-0 text-white text-xs px-3 py-1.5 rounded-lg transition-all font-medium flex items-center gap-1 shadow-sm"
                  >
                    {showAddPortfolio ? <X size={14} /> : <Plus size={14} />}
                    {showAddPortfolio ? 'Отмена' : 'Добавить'}
                  </button>
                </div>

                {/* Add Portfolio Form */}
                {showAddPortfolio && (
                  <form
                    onSubmit={handleAddPortfolio}
                    className="glass-card border-[#005BB3]/30 p-4 rounded-xl space-y-3 shadow-md animate-fadeIn font-body"
                  >
                    <h3 className="font-heading text-sm font-semibold text-[#D8226C]">Новый проект</h3>
                    <div>
                      <label className="block text-xs text-slate-700 mb-1 font-medium">Название проекта *</label>
                      <input
                        type="text"
                        required
                        value={portTitle}
                        onChange={(e) => setPortTitle(e.target.value)}
                        placeholder="Showreel 2026 или Проморолик"
                        className="w-full bg-slate-50 text-slate-900 p-2 rounded-lg border border-slate-200 focus:outline-none focus:border-[#005BB3] focus:bg-white text-xs font-body"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-slate-700 mb-1 font-medium">Ссылка на проект (YouTube, Behance, Диск) *</label>
                      <input
                        type="url"
                        required
                        value={portUrl}
                        onChange={(e) => setPortUrl(e.target.value)}
                        placeholder="https://..."
                        className="w-full bg-slate-50 text-slate-900 p-2 rounded-lg border border-slate-200 focus:outline-none focus:border-[#005BB3] focus:bg-white text-xs font-body"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-slate-700 mb-1 font-medium">Описание проекта</label>
                      <textarea
                        rows={2}
                        value={portDesc}
                        onChange={(e) => setPortDesc(e.target.value)}
                        placeholder="Какие задачи решили и какого результата достигли..."
                        className="w-full bg-slate-50 text-slate-900 p-2 rounded-lg border border-slate-200 focus:outline-none focus:border-[#005BB3] focus:bg-white text-xs font-body resize-none"
                      />
                    </div>
                    <button
                      type="submit"
                      disabled={addingPortfolio}
                      className="w-full font-body bg-[#005BB3] hover:bg-[#004b94] hover:-translate-y-0.5 active:translate-y-0 disabled:opacity-50 text-white font-medium py-2 rounded-lg transition-all text-xs shadow-sm flex items-center justify-center gap-1.5"
                    >
                      {addingPortfolio ? <Loader2 className="animate-spin" size={14} /> : <Plus size={14} />}
                      Сохранить проект
                    </button>
                  </form>
                )}

                {/* Portfolio List */}
                {portfolio.length === 0 ? (
                  <div className="glass-card glass-card-hover p-6 rounded-xl text-center space-y-3 shadow-sm font-body">
                    <div className="w-12 h-12 bg-[#B2DAE4]/30 text-[#005BB3] rounded-full flex items-center justify-center mx-auto border border-[#B2DAE4]">
                      <Briefcase size={24} />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-slate-800">Вы ещё не добавили проекты</p>
                      <p className="text-xs text-slate-500 mt-1">
                        Добавьте ссылки на проекты, YouTube или Behance — нейросеть будет прикладывать подходящие кейсы к отклику.
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {portfolio.map((item) => (
                      <div
                        key={item.id}
                        className="glass-card glass-card-hover p-4 rounded-xl flex justify-between items-start space-x-3 shadow-sm hover:-translate-y-0.5 transition-all duration-200 font-body"
                      >
                        <div className="flex-1 min-w-0">
                          <h4 className="font-heading font-semibold text-sm text-slate-900 truncate">{item.title}</h4>
                          <a
                            href={item.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-[#005BB3] hover:underline flex items-center gap-1 mt-0.5 truncate font-body"
                          >
                            <ExternalLink size={12} />
                            {item.url}
                          </a>
                          {item.description && (
                            <p className="text-xs text-slate-600 mt-1.5 line-clamp-2 font-body">{item.description}</p>
                          )}
                        </div>
                        <button
                          onClick={() => handleDeletePortfolio(item.id)}
                          className="text-slate-400 hover:text-[#D8226C] p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
                          title="Удалить кейс"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* CHANNELS TAB */}
            {activeTab === 'channels' && (
              <div className="space-y-4 animate-fadeIn">
                <h2 className="font-heading text-lg font-semibold flex items-center gap-2 text-slate-900">
                  <Radio size={20} className="text-[#005BB3]" /> Каналы & Источники
                </h2>

                <div className="glass-card glass-card-hover p-4 rounded-xl space-y-4 shadow-sm font-body">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-medium text-slate-600">Мониторинг каналов вакансий:</p>
                    <span className="text-[10px] text-slate-500 font-medium">
                      {channels.filter((c) => c.is_enabled).length} из {channels.length} активны
                    </span>
                  </div>

                  {/* Channel List */}
                  <div className="space-y-2">
                    {channels.map((ch) => (
                      <div
                        key={ch.id}
                        className={`flex items-center justify-between p-3 rounded-xl border transition-all hover:-translate-y-0.5 ${
                          ch.is_enabled
                            ? 'bg-white border-slate-200 shadow-sm'
                            : 'bg-slate-50 border-slate-200 opacity-60'
                        }`}
                      >
                        <div className="min-w-0 pr-2 font-body">
                          <p className="text-sm font-medium text-slate-900 truncate">
                            📢 {ch.title || `@${ch.username}`}
                          </p>
                          <p className="text-[11px] text-slate-500 truncate">@{ch.username}</p>
                        </div>
                        <label className="relative inline-flex items-center cursor-pointer">
                          <input
                            type="checkbox"
                            checked={ch.is_enabled}
                            onChange={() => handleToggleChannel(ch.id, ch.is_enabled)}
                            className="sr-only peer"
                          />
                          <div className="w-9 h-5 bg-slate-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-[#005BB3]"></div>
                        </label>
                      </div>
                    ))}
                  </div>

                  {/* Add Custom Channel Form */}
                  <form onSubmit={handleAddCustomChannel} className="pt-2 border-t border-slate-200 space-y-2 font-body">
                    <label className="block text-xs font-medium text-slate-700">Добавить свой канал Telegram</label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={customChannelInput}
                        onChange={(e) => setCustomChannelInput(e.target.value)}
                        placeholder="@channel_name или t.me/channel"
                        className="flex-1 bg-slate-50 text-slate-900 px-3 py-2 rounded-lg border border-slate-200 focus:outline-none focus:border-[#005BB3] focus:bg-white text-xs font-body"
                      />
                      <button
                        type="submit"
                        disabled={addingChannel}
                        className="font-body bg-[#005BB3] hover:bg-[#004b94] hover:-translate-y-0.5 active:translate-y-0 disabled:opacity-50 text-white text-xs px-3 py-2 rounded-lg transition-all font-medium flex items-center gap-1 shadow-sm"
                      >
                        {addingChannel ? <Loader2 className="animate-spin" size={14} /> : <Plus size={14} />}
                        Добавить
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            )}

            {/* SUBSCRIPTION TAB */}
            {activeTab === 'subscription' && (
              <div className="space-y-4 animate-fadeIn pb-6 font-body">
                <h2 className="font-heading text-lg font-semibold flex items-center gap-2 text-slate-900">
                  <CreditCard size={20} className="text-[#005BB3]" /> Подписка & Тарифы
                </h2>

                {/* Plan Selection Cards */}
                <div className="grid grid-cols-2 gap-3">
                  {/* PRO Неделя */}
                  <div
                    onClick={() => {
                      triggerHaptic('light');
                      setSelectedPlan('week');
                    }}
                    className={`cursor-pointer rounded-xl p-4 border transition-all duration-200 hover:-translate-y-1 relative flex flex-col justify-between ${
                      selectedPlan === 'week'
                        ? 'bg-[#005BB3]/10 border-[#005BB3] ring-1 ring-[#005BB3] shadow-sm'
                        : 'bg-white border-slate-200 hover:border-slate-300 shadow-sm'
                    }`}
                  >
                    {selectedPlan === 'week' && (
                      <div className="absolute top-2 right-2 w-4 h-4 rounded-full bg-[#005BB3] flex items-center justify-center">
                        <Check size={10} className="text-white stroke-[3]" />
                      </div>
                    )}
                    <div>
                      <span className="font-body text-[10px] font-bold tracking-wider px-2 py-0.5 rounded bg-[#005BB3]/15 text-[#005BB3] uppercase">
                        7 Дней
                      </span>
                      <h3 className="font-heading font-bold text-base text-slate-900 mt-2">Неделя</h3>
                      <p className="font-body text-xs text-slate-500 mt-1">Для проверки работы бота</p>
                    </div>
                    <div className="mt-4 pt-3 border-t border-slate-200">
                      <div className="font-heading text-lg font-bold text-slate-900">300 ₽</div>
                      <div className="font-body text-[11px] text-slate-500 mt-0.5">Карта РФ</div>
                    </div>
                  </div>

                  {/* Месяц */}
                  <div
                    onClick={() => {
                      triggerHaptic('light');
                      setSelectedPlan('month');
                    }}
                    className={`cursor-pointer rounded-xl p-4 border transition-all duration-200 hover:-translate-y-1 relative flex flex-col justify-between ${
                      selectedPlan === 'month'
                        ? 'bg-[#F86A38]/10 border-[#F86A38] ring-1 ring-[#F86A38] shadow-sm'
                        : 'bg-white border-slate-200 hover:border-slate-300 shadow-sm'
                    }`}
                  >
                    <div className="absolute -top-2.5 right-3 bg-gradient-to-r from-[#F86A38] to-[#D8226C] text-white font-bold text-[9px] px-2.5 py-0.5 rounded-full shadow-sm font-heading">
                      ВЫГОДНО
                    </div>
                    {selectedPlan === 'month' && (
                      <div className="absolute top-2 right-2 w-4 h-4 rounded-full bg-[#F86A38] flex items-center justify-center">
                        <Check size={10} className="text-white stroke-[3]" />
                      </div>
                    )}
                    <div>
                      <span className="font-body text-[10px] font-bold tracking-wider px-2 py-0.5 rounded bg-[#F86A38]/15 text-[#e04e1b] uppercase">
                        30 Дней
                      </span>
                      <h3 className="font-heading font-bold text-base text-slate-900 mt-2">Месяц</h3>
                      <p className="font-body text-xs text-slate-500 mt-1">Постоянный поиск и отправка откликов</p>
                    </div>
                    <div className="mt-4 pt-3 border-t border-slate-200">
                      <div className="font-heading text-lg font-bold text-slate-900">600 ₽</div>
                      <div className="font-body text-[11px] text-slate-500 mt-0.5">Карта РФ</div>
                    </div>
                  </div>
                </div>

                {/* Selected Plan Details & Payment Card */}
                <div className="glass-card glass-card-hover p-4 rounded-xl border border-slate-200 space-y-4 shadow-sm font-body">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-xs text-slate-500">Выбранный тариф:</span>
                      <h4 className="font-heading text-sm font-bold text-slate-900">
                        {selectedPlan === 'week' ? 'Неделя (300 ₽ на 7 дней)' : 'Месяц (600 ₽ на 30 дней)'}
                      </h4>
                    </div>
                    <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-[#005BB3]/10 text-[#005BB3] border border-[#005BB3]/20">
                      {selectedPlan === 'week' ? '300 ₽' : '600 ₽'}
                    </span>
                  </div>

                  {/* Payment via Card Details */}
                  <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-3">
                    <div className="flex items-center justify-between text-xs text-slate-600">
                      <span>Оплата переводом на карту:</span>
                      <span className="text-[10px] bg-slate-200 px-2 py-0.5 rounded text-slate-700 font-medium">РФ Карты</span>
                    </div>

                    {/* Card visual display */}
                    <div className="bg-white p-3.5 rounded-lg border border-slate-200 flex items-center justify-between shadow-sm">
                      <div className="font-mono text-base font-bold text-slate-900 tracking-wider">
                        2203 3101 8911 3452
                      </div>
                      <button
                        type="button"
                        onClick={handleCopyCard}
                        className="bg-slate-100 hover:bg-slate-200 hover:-translate-y-0.5 active:translate-y-0 text-slate-700 text-xs px-2.5 py-1.5 rounded-md border border-slate-300 transition-all flex items-center gap-1.5 shrink-0 font-medium"
                      >
                        {copiedCard ? (
                          <>
                            <Check size={14} className="text-[#029456]" />
                            <span className="text-[#029456] font-semibold">Скопировано</span>
                          </>
                        ) : (
                          <>
                            <Copy size={14} />
                            <span>Скопировать карту</span>
                          </>
                        )}
                      </button>
                    </div>

                    <div className="space-y-2 pt-1">
                      <div className="flex items-center justify-between">
                        <label className="block text-[11px] font-medium text-slate-700">
                          Прикрепите чек оплаты (PDF или фото) <span className="text-[#D8226C]">*</span>
                        </label>
                        <input
                          type="file"
                          accept=".pdf,image/png,image/jpeg,image/jpg,image/webp"
                          ref={receiptFileInputRef}
                          onChange={handleReceiptFileSelect}
                          className="hidden"
                        />
                        <button
                          type="button"
                          onClick={() => {
                            triggerHaptic('light');
                            receiptFileInputRef.current?.click();
                          }}
                          className="text-xs bg-[#005BB3]/10 hover:bg-[#005BB3]/20 text-[#005BB3] border border-[#005BB3]/30 px-2.5 py-1 rounded-md transition-all font-medium flex items-center gap-1"
                        >
                          <Upload size={12} />
                          <span>Прикрепить файл</span>
                        </button>
                      </div>

                      {receiptFile ? (
                        <div className="flex items-center justify-between p-2 bg-[#005BB3]/5 border border-[#005BB3]/20 rounded-lg text-xs font-body">
                          <span className="font-medium text-[#005BB3] truncate flex items-center gap-1">
                            📄 {receiptFile.name}
                          </span>
                          <button
                            type="button"
                            onClick={() => setReceiptFile(null)}
                            className="text-slate-400 hover:text-[#D8226C] p-0.5 ml-2"
                          >
                            <X size={14} />
                          </button>
                        </div>
                      ) : (
                        <p className="text-[10px] text-slate-500 font-body">
                          Максимальный размер файла — 10 МБ
                        </p>
                      )}

                      <textarea
                        rows={2}
                        value={receiptInfo}
                        onChange={(e) => setReceiptInfo(e.target.value)}
                        placeholder="Дополнительно: ссылка на чек, ФИО отправителя или номер перевода..."
                        className="w-full bg-white text-slate-900 p-2.5 rounded-lg border border-slate-200 text-xs font-body focus:outline-none focus:border-[#005BB3] placeholder:text-slate-400"
                      />
                    </div>

                    {/* Request Card Submit Button */}
                    <button
                      type="button"
                      onClick={handleRequestCard}
                      disabled={submittingCardRequest}
                      className="w-full bg-[#D8226C] hover:bg-[#b81b5b] hover:-translate-y-0.5 active:translate-y-0 disabled:opacity-50 text-white font-semibold py-2.5 rounded-xl transition-all shadow-md text-xs flex items-center justify-center gap-2 font-body"
                    >
                      {submittingCardRequest ? (
                        <>
                          <Loader2 size={16} className="animate-spin" />
                          <span>Отправка запроса...</span>
                        </>
                      ) : (
                        <>
                          <Send size={15} />
                          <span>Я перевёл</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            )}
            {/* ADMIN TAB */}
            {activeTab === 'admin' && <AdminPanel />}
          </>
        )}
      </div>

      {/* Bottom Navigation */}
      <div className="fixed bottom-0 left-0 right-0 bg-white/95 backdrop-blur-md border-t border-slate-200 py-2.5 px-4 z-50 shadow-lg">
        <div className="flex justify-around max-w-md mx-auto">
          <button
            onClick={() => handleTabChange('profile')}
            className={`flex flex-col items-center gap-1 text-xs font-body transition-colors ${
              activeTab === 'profile' ? 'text-[#005BB3] font-semibold' : 'text-slate-500 hover:text-[#005BB3]'
            }`}
          >
            <User size={20} />
            <span>Профиль</span>
          </button>
          <button
            onClick={() => handleTabChange('portfolio')}
            className={`flex flex-col items-center gap-1 text-xs font-body transition-colors ${
              activeTab === 'portfolio' ? 'text-[#005BB3] font-semibold' : 'text-slate-500 hover:text-[#005BB3]'
            }`}
          >
            <Briefcase size={20} />
            <span>Портфолио</span>
          </button>
          <button
            onClick={() => handleTabChange('channels')}
            className={`flex flex-col items-center gap-1 text-xs font-body transition-colors ${
              activeTab === 'channels' ? 'text-[#005BB3] font-semibold' : 'text-slate-500 hover:text-[#005BB3]'
            }`}
          >
            <Radio size={20} />
            <span>Чаты</span>
          </button>
          <button
            onClick={() => handleTabChange('subscription')}
            className={`flex flex-col items-center gap-1 text-xs font-body transition-colors ${
              activeTab === 'subscription' ? 'text-[#005BB3] font-semibold' : 'text-slate-500 hover:text-[#005BB3]'
            }`}
          >
            <CreditCard size={20} />
            <span>Тарифы</span>
          </button>

          {isAdmin && (
            <button
              onClick={() => handleTabChange('admin')}
              className={`flex flex-col items-center gap-1 text-xs font-body transition-colors ${
                activeTab === 'admin' ? 'text-[#005BB3] font-semibold' : 'text-slate-500 hover:text-[#005BB3]'
              }`}
            >
              <AdminShieldIcon size={20} className={activeTab === 'admin' ? 'text-[#005BB3]' : 'text-slate-500'} />
              <span>Админка</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
