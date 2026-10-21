import { logEvent, Analytics } from "firebase/analytics";
import { analytics } from "./firebase";

// Track page views
export const trackPageView = (page_title: string, page_location: string) => {
  if (analytics) {
    logEvent(analytics, 'page_view', {
      page_title,
      page_location,
    });
  }
};

// Track custom events
export const trackEvent = (event_name: string, parameters?: Record<string, any>) => {
  if (analytics) {
    logEvent(analytics, event_name, parameters);
  }
};

// Track story events
export const trackStoryEvent = (action: string) => {
  if (analytics) {
    logEvent(analytics, 'story_interaction', {
      action,
    });
  }
};

// Track user engagement
export const trackUserEngagement = (engagement_time_msec: number) => {
  if (analytics) {
    logEvent(analytics, 'user_engagement', {
      engagement_time_msec,
    });
  }
};

// Track conversion events
export const trackConversion = (conversion_type: string, value?: number, currency?: string) => {
  if (analytics) {
    logEvent(analytics, 'conversion', {
      conversion_type,
      value,
      currency: currency || 'USD',
    });
  }
};

// Track funnel steps
export const trackFunnelStep = (step_name: string, step_number: number, total_steps: number) => {
  if (analytics) {
    logEvent(analytics, 'funnel_step', {
      step_name,
      step_number,
      total_steps,
      progress_percentage: Math.round((step_number / total_steps) * 100),
    });
  }
};

// Track user journey
export const trackUserJourney = (journey_step: string, time_spent?: number) => {
  if (analytics) {
    logEvent(analytics, 'user_journey', {
      journey_step,
      time_spent,
      timestamp: Date.now(),
    });
  }
};

// Track feature usage
export const trackFeatureUsage = (feature_name: string, usage_count?: number) => {
  if (analytics) {
    logEvent(analytics, 'feature_usage', {
      feature_name,
      usage_count: usage_count || 1,
    });
  }
}; 
