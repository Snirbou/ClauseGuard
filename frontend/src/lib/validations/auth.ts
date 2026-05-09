import { z } from "zod";

export const loginSchema = z.object({
  email: z.email({ error: "Enter a valid email" }).trim(),
  password: z.string().min(1, "Password is required"),
});

export const signupSchema = z
  .object({
    email: z.email({ error: "Enter a valid email" }).trim(),
    fullName: z
      .string()
      .max(120, "Full name is too long")
      .trim()
      .optional()
      .or(z.literal("")),
    password: z
      .string()
      .min(8, "At least 8 characters")
      .regex(/[A-Za-z]/, "Must contain a letter")
      .regex(/[0-9]/, "Must contain a number"),
    confirmPassword: z.string().min(1, "Confirm your password"),
  })
  .refine((d) => d.password === d.confirmPassword, {
    message: "Passwords do not match",
    path: ["confirmPassword"],
  });

export type LoginValues = z.infer<typeof loginSchema>;
export type SignupValues = z.infer<typeof signupSchema>;
