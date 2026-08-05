/**
 * REST API Client for Vacancy Spotter Telegram Mini App.
 * Wraps fetch requests with Telegram WebApp authorization headers.
 */

export interface UserProfile {
  user_id: number;
  username?: string | null;
  first_name: string;
  profession_id: string;
  experience_years: number;
  location: string;
  stop_words: string[];
  subscription_status: 'demo' | 'active' | 'expired';
  demo_until: string;
  subscription_until?: string | null;
  bio_summary: string;
  software_stack: string[];
}

export interface UserProfileUpdate {
  profession_id?: string;
  experience_years?: number;
  location?: string;
  stop_words?: string[];
  bio_summary?: string;
  software_stack?: string[];
}

export interface PortfolioItem {
  id: number;
  user_id: number;
  title: string;
  url: string;
  category: string;
  orientation: 'horizontal' | 'vertical';
  description: string;
  tags: string[];
  created_at: string;
}

export interface PortfolioItemCreate {
  title: string;
  url: string;
  category?: string;
  orientation?: 'horizontal' | 'vertical';
  description: string;
  tags?: string[];
}

export interface Channel {
  id: number;
  profession_id: string;
  username: string;
  title: string;
  is_recommended: boolean;
  is_enabled: boolean;
}

export interface ToggleChannelRequest {
  channel_id: number;
  is_enabled: boolean;
}

export interface Profession {
  id: string;
  title_ru: string;
  icon_emoji: string;
}

export type JobCardStatus = 'new' | 'saved' | 'applied' | 'rejected' | 'hidden';

export interface JobCard {
  id: number;
  user_id: number;
  channel_title: string;
  channel_username: string;
  post_text: string;
  post_url: string;
  post_date?: string | null;
  status: JobCardStatus;
  match_score: number;
  matched_keywords: string[];
  draft_reply: string;
  created_at: string;
}

export interface AdminUser {
  user_id: number;
  username?: string | null;
  first_name: string;
  profession_id: string;
  subscription_status: string;
  demo_until: string;
  subscription_until?: string | null;
  is_banned: boolean;
  ban_reason?: string | null;
  channels_count: number;
  created_at: string;
}

export interface AdminStats {
  total_users: number;
  active_paid_users: number;
  demo_users: number;
  expired_users: number;
  banned_users: number;
}

export interface AdminUserDetail {
  profile: UserProfile;
  is_banned: boolean;
  ban_reason?: string | null;
  bio_summary: string;
  software_stack: string[];
  stop_words: string[];
  connected_channels: Array<{
    channel_id: number;
    username: string;
    title: string;
    profession_id: string;
    is_enabled: boolean;
  }>;
  created_at: string;
}

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function getHeaders(): Record<string, string> {
  const tg = (window as any).Telegram?.WebApp;
  const initData = tg?.initData || 'dev_mode_965000782';
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${initData}`,
  };
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      ...getHeaders(),
      ...(options.headers || {}),
    },
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`API Error (${response.status}): ${errorText}`);
  }

  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) {
    throw new Error(`Сервер вернул HTML вместо JSON. Убедитесь, что бэкенд доступен по адресу ${url}`);
  }

  return response.json();
}

export const api = {
  // Profile
  getProfile: (): Promise<UserProfile> => request<UserProfile>('/api/profile'),
  updateProfile: (dto: UserProfileUpdate): Promise<UserProfile> =>
    request<UserProfile>('/api/profile', {
      method: 'PUT',
      body: JSON.stringify(dto),
    }),

  // Portfolio
  getPortfolio: (): Promise<PortfolioItem[]> => request<PortfolioItem[]>('/api/portfolio'),
  addPortfolioItem: (dto: PortfolioItemCreate): Promise<PortfolioItem> =>
    request<PortfolioItem>('/api/portfolio', {
      method: 'POST',
      body: JSON.stringify(dto),
    }),
  deletePortfolioItem: (id: number): Promise<{ status: string; deleted_id: number }> =>
    request<{ status: string; deleted_id: number }>(`/api/portfolio/${id}`, {
      method: 'DELETE',
    }),

  // Channels
  getChannels: (): Promise<Channel[]> => request<Channel[]>('/api/channels'),
  toggleChannel: (channel_id: number, is_enabled: boolean): Promise<{ status: string; channel_id: number; is_enabled: boolean }> =>
    request('/api/channels/toggle', {
      method: 'POST',
      body: JSON.stringify({ channel_id, is_enabled }),
    }),
  addCustomChannel: (username_or_link: string): Promise<Channel> =>
    request<Channel>('/api/channels/custom', {
      method: 'POST',
      body: JSON.stringify({ username_or_link }),
    }),

  // Professions
  getProfessions: (): Promise<Profession[]> => request<Profession[]>('/api/professions'),

  // Subscription
  requestCardSubscription: (
    plan: 'week' | 'month',
    receipt_info: string = '',
    receipt_file_b64?: string | null,
    receipt_filename?: string | null,
  ): Promise<{ status: string; message: string }> =>
    request<{ status: string; message: string }>('/api/subscription/request_card', {
      method: 'POST',
      body: JSON.stringify({
        plan,
        receipt_info,
        receipt_file_b64: receipt_file_b64 || null,
        receipt_filename: receipt_filename || null,
      }),
    }),

  // Parse Resume PDF
  parseResumePdf: async (file: File): Promise<{ extracted_text: string }> => {
    const formData = new FormData();
    formData.append('file', file);
    const tg = (window as any).Telegram?.WebApp;
    const initData = tg?.initData || 'dev_mode_965000782';
    const response = await fetch(`${BASE_URL}/api/profile/parse_pdf`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${initData}`,
      },
      body: formData,
    });
    if (!response.ok) {
      const err = await response.text();
      throw new Error(err);
    }
    return response.json();
  },

  // Job Cards (vacancies & draft replies)
  getCards: (status?: JobCardStatus): Promise<JobCard[]> =>
    request<JobCard[]>(`/api/cards${status ? `?status_filter=${status}` : ''}`),
  updateCardStatus: (cardId: number, status: JobCardStatus): Promise<JobCard> =>
    request<JobCard>(`/api/cards/${cardId}/status`, {
      method: 'PUT',
      body: JSON.stringify({ status }),
    }),
  regenerateCardDraft: (cardId: number, customInstruction: string = ''): Promise<JobCard> =>
    request<JobCard>(`/api/cards/${cardId}/regenerate`, {
      method: 'POST',
      body: JSON.stringify({ custom_instruction: customInstruction }),
    }),

  // Admin API
  checkAdmin: (): Promise<{ is_admin: boolean; user_id: number }> =>
    request<{ is_admin: boolean; user_id: number }>('/api/admin/check'),
  getAdminStats: (): Promise<AdminStats> => request<AdminStats>('/api/admin/stats'),
  getAdminUsers: (page = 1, limit = 20, search = '', status = 'all'): Promise<{ items: AdminUser[]; total: number; page: number; limit: number; pages: number }> =>
    request(`/api/admin/users?page=${page}&limit=${limit}&search=${encodeURIComponent(search)}&status=${status}`),
  getAdminUserDetail: (userId: number): Promise<AdminUserDetail> =>
    request<AdminUserDetail>(`/api/admin/users/${userId}`),
  updateAdminUserSubscription: (userId: number, dto: { action: 'add_days' | 'set_status' | 'revoke'; days?: number; status?: string }): Promise<UserProfile> =>
    request<UserProfile>(`/api/admin/users/${userId}/subscription`, {
      method: 'POST',
      body: JSON.stringify(dto),
    }),
  updateAdminUserBan: (userId: number, dto: { is_banned: boolean; ban_reason?: string }): Promise<{ status: string; is_banned: boolean; ban_reason?: string }> =>
    request(`/api/admin/users/${userId}/ban`, {
      method: 'POST',
      body: JSON.stringify(dto),
    }),
};
