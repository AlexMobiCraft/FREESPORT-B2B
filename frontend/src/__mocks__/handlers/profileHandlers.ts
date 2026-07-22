import { http, HttpResponse } from 'msw';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api/v1';

export const profileHandlers = [
  // GET Profile
  http.get(`${API_BASE_URL}/users/profile/`, () => {
    return HttpResponse.json({
      id: 1,
      email: 'test@example.com',
      first_name: 'Test',
      last_name: 'User',
      phone: '+79001234567',
      role: 'retail',
      is_verified: true,
      company_name: null,
      tax_id: null,
    });
  }),

  // PUT Profile
  http.put(`${API_BASE_URL}/users/profile/`, async ({ request }) => {
    const body = (await request.json()) as {
      first_name?: string;
      last_name?: string;
      phone?: string;
    };

    // Simulate validation error
    if (!body.first_name) {
      return HttpResponse.json({ first_name: ['This field is required.'] }, { status: 400 });
    }

    return HttpResponse.json({
      id: 1,
      email: 'test@example.com',
      first_name: body.first_name,
      last_name: body.last_name,
      phone: body.phone,
      role: 'retail',
      is_verified: true,
      company_name: null,
      tax_id: null,
    });
  }),
];
