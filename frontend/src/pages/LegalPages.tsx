import type { ReactNode } from 'react'

const CONTACT_EMAIL = 'admin@mainspring.au'
const COMPANY = 'Unamigo Pty Ltd'
const LAST_UPDATED = '1 October 2026'

function LegalLayout({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[#F7F5F0] text-[#1B2B3E]">
      <main className="mx-auto max-w-3xl px-5 py-10">
        <a href="/" className="text-sm font-semibold text-[#B8321E]">Mainspring</a>
        <h1 className="mt-3 text-3xl font-semibold">{title}</h1>
        <p className="mt-1 text-sm text-[#5C6670]">Last updated {LAST_UPDATED}</p>
        <div className="mt-8 space-y-6 text-[15px] leading-7 [&_h2]:mt-8 [&_h2]:text-xl [&_h2]:font-semibold [&_ul]:list-disc [&_ul]:pl-6 [&_a]:text-[#B8321E] [&_a]:underline">
          {children}
        </div>
      </main>
    </div>
  )
}

export function PrivacyPolicyPage() {
  return (
    <LegalLayout title="Privacy Policy">
      <p>
        Mainspring (the website at mainspring.au and the Mainspring mobile app) is operated by {COMPANY}
        (&ldquo;we&rdquo;, &ldquo;us&rdquo;). Mainspring is business software that repair shops use to manage watch,
        shoe and key repair jobs, quotes, invoices and customers. This policy explains what personal information we
        handle and why. We handle it in line with the Australian Privacy Principles in the Privacy Act 1988 (Cth).
      </p>

      <h2>Two kinds of people</h2>
      <ul>
        <li><strong>Shop staff and owners</strong> who sign in to Mainspring. We hold your account details.</li>
        <li><strong>Customers of a shop.</strong> A shop enters your details so it can repair your item and contact you.
          The shop decides what it records about you and why. We process that information on the shop&rsquo;s behalf.
          To see, correct or delete what a shop holds about you, contact the shop first.</li>
      </ul>

      <h2>What we collect</h2>
      <ul>
        <li><strong>Account information:</strong> name, email address, mobile number (if provided), role, shop name and a
          securely hashed password.</li>
        <li><strong>Shop records:</strong> customer names, phone numbers, email addresses and addresses, details of
          items and repairs, notes, quotes, invoices, payments, and messages sent through Mainspring.</li>
        <li><strong>Photos and files</strong> that staff attach to jobs. The mobile app asks for camera permission so
          staff can photograph items; photos are only taken and uploaded when a person chooses to.</li>
        <li><strong>Device information for notifications:</strong> if you allow notifications in the mobile app, we store
          a push notification token for your device so we can alert you to new activity in your shop.</li>
        <li><strong>Technical and security information:</strong> sign-in events, IP address, browser or device type,
          and error reports that help us keep the service secure and working.</li>
        <li><strong>Location and map searches:</strong> where a shop uses address search or mobile-service routing,
          addresses typed into those features are sent to our mapping provider.</li>
      </ul>
      <p>We do not sell personal information and we do not use it for third-party advertising.</p>

      <h2>How we use it</h2>
      <ul>
        <li>To provide Mainspring: run jobs, send quotes and invoices, take payments and send updates to customers.</li>
        <li>To send notifications, emails and text messages that a shop triggers or you have asked for.</li>
        <li>To secure the service, prevent fraud and fix problems.</li>
        <li>To bill shops for their subscription and meet our legal obligations.</li>
      </ul>

      <h2>Who we share it with</h2>
      <p>We use service providers to run Mainspring. They may process information only to provide their service to us:</p>
      <ul>
        <li>Hosting and database: Railway, and file storage: Supabase.</li>
        <li>Payments: Stripe.</li>
        <li>Email and text messages: SendGrid and Twilio.</li>
        <li>Push notifications: Google Firebase Cloud Messaging.</li>
        <li>Maps and address search: Google.</li>
        <li>Error monitoring: Sentry.</li>
        <li>Accounting: Xero, only where a shop chooses to connect it.</li>
      </ul>
      <p>
        Some of these providers store or process data outside Australia, including in the United States and
        Singapore. We take reasonable steps to make sure they protect it. We may also disclose information where the law
        requires it, or to a successor if our business is sold.
      </p>

      <h2>Keeping it safe and how long we keep it</h2>
      <p>
        Data is encrypted in transit, passwords are hashed, and access is limited by shop and by role. No system is
        perfectly secure. We keep shop records while the shop&rsquo;s account is active and for a reasonable period afterwards
        for tax, legal and dispute purposes, then delete or de-identify them.
      </p>

      <h2>Your choices and rights</h2>
      <ul>
        <li>You can ask us for access to, or correction of, personal information we hold about you.</li>
        <li>You can turn off notifications in your phone&rsquo;s settings, and revoke camera permission at any time.</li>
        <li>You can ask us to delete your account and data. See <a href="/delete-account">how to request deletion</a>.</li>
        <li>If you are unhappy with how we handled your information, contact us. If we cannot resolve it, you can complain
          to the Office of the Australian Information Commissioner (oaic.gov.au).</li>
      </ul>

      <h2>Children</h2>
      <p>Mainspring is for businesses and is not directed at children under 16.</p>

      <h2>Changes</h2>
      <p>We may update this policy. The date above shows when it last changed; we will give notice of material changes.</p>

      <h2>Contact</h2>
      <p>
        {COMPANY}<br />
        Email: <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
      </p>
    </LegalLayout>
  )
}

export function AccountDeletionPage() {
  const subject = encodeURIComponent('Mainspring account deletion request')
  return (
    <LegalLayout title="Delete your Mainspring account">
      <p>
        You can ask {COMPANY} to delete your Mainspring account and the personal information linked to it.
      </p>

      <h2>How to request deletion</h2>
      <ol className="list-decimal space-y-1 pl-6">
        <li>
          Email <a href={`mailto:${CONTACT_EMAIL}?subject=${subject}`}>{CONTACT_EMAIL}</a> from the email address on the
          account, with the subject &ldquo;Mainspring account deletion request&rdquo;.
        </li>
        <li>Include your shop ID (the shop name you sign in with) and say whether you want only your own login deleted or
          the whole shop account.</li>
        <li>We may reply to confirm it is really you before we act.</li>
      </ol>

      <h2>What happens next</h2>
      <ul>
        <li>We act on verified requests within 30 days.</li>
        <li>Your login, profile details and push notification tokens are deleted.</li>
        <li>If you ask for a whole shop to be deleted, its customer records, jobs, photos and files are deleted too.
          This cannot be undone, so export anything you need first.</li>
        <li>We may keep limited records we are legally required to keep, such as invoices and payment records, for the
          period the law requires, and then delete them.</li>
      </ul>

      <p>
        Customers of a shop who want their details removed should contact that shop. See our{' '}
        <a href="/privacy">Privacy Policy</a> for more.
      </p>
    </LegalLayout>
  )
}

export default PrivacyPolicyPage
