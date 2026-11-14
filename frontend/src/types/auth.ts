export interface AuthUser {
  id: string;
  email: string;
  email_verified: boolean;
  name: string | null;
  picture: string | null;
}

export interface AuthSession {
  authenticated: boolean;
  user: AuthUser | null;
  access_token: string | null;
  token_type: string | null;
  expires_in: number | null;
}
