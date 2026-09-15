'use client';

import type { CandidateProfile } from '@trema/api-client';
import { GripVertical, Plus, Save, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Controller, useFieldArray, useForm, type Control, type UseFormRegister } from 'react-hook-form';

import { Button } from '@/components/ui/button';
import { Field } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { ListInput } from '@/components/ui/list-input';
import { Tabs } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';

type Section = 'identity' | 'experiences' | 'projects' | 'skills' | 'education';

interface ProfileFormProps {
  profile: CandidateProfile;
  saving: boolean;
  onSave: (profile: CandidateProfile) => void;
}

/** Identifiants stables pour les nouvelles entrées (référencés par les CV générés). */
function nextId(prefix: string, existing: { id: string }[]) {
  const max = existing.reduce((m, e) => {
    const n = Number(e.id.replace(/^\D+/, ''));
    return Number.isFinite(n) ? Math.max(m, n) : m;
  }, 0);
  return `${prefix}_${String(max + 1).padStart(3, '0')}`;
}

export function ProfileForm({ profile, saving, onSave }: ProfileFormProps) {
  const [section, setSection] = useState<Section>('identity');
  const form = useForm<CandidateProfile>({ defaultValues: profile });
  const { register, control, handleSubmit, reset, formState } = form;

  // Après une transcription IA ou un rechargement, le formulaire repart des données serveur.
  useEffect(() => reset(profile), [profile, reset]);

  const experiences = useFieldArray({ control, name: 'experiences', keyName: '_key' });
  const projects = useFieldArray({ control, name: 'projects', keyName: '_key' });
  const education = useFieldArray({ control, name: 'education', keyName: '_key' });

  return (
    <form onSubmit={handleSubmit(onSave)} className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4">
        <Tabs<Section>
          className="border-b-0"
          value={section}
          onChange={setSection}
          items={[
            { value: 'identity', label: 'Identité' },
            { value: 'experiences', label: `Expériences (${experiences.fields.length})` },
            { value: 'projects', label: `Projets (${projects.fields.length})` },
            { value: 'skills', label: 'Compétences' },
            { value: 'education', label: 'Formation & langues' },
          ]}
        />
        <div className="flex items-center gap-3 py-2">
          {formState.isDirty ? <span className="text-xs text-amber-600">Modifications non enregistrées</span> : null}
          <Button type="submit" size="sm" loading={saving} disabled={!formState.isDirty}>
            <Save /> Enregistrer
          </Button>
        </div>
      </div>

      <div className="p-5">
        {/* ---------------- Identité ---------------- */}
        <div className={section === 'identity' ? 'space-y-5' : 'hidden'}>
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Prénom" htmlFor="first_name">
              <Input id="first_name" {...register('personal.first_name', { required: true })} />
            </Field>
            <Field label="Nom" htmlFor="last_name">
              <Input id="last_name" {...register('personal.last_name', { required: true })} />
            </Field>
            <Field label="Nom affiché" htmlFor="name" hint="Utilisé dans les fiches Notion et les noms de fichiers">
              <Input id="name" {...register('name', { required: true })} />
            </Field>
            <Field label="Titre professionnel" htmlFor="title" hint="Titre par défaut du CV, adapté à chaque offre par l’IA">
              <Input id="title" {...register('title')} />
            </Field>
            <Field label="E-mail" htmlFor="email">
              <Input id="email" type="email" {...register('personal.email', { required: true })} />
            </Field>
            <Field label="Téléphone" htmlFor="phone">
              <Input id="phone" {...register('personal.phone')} />
            </Field>
            <Field label="Localisation / mobilité" htmlFor="location">
              <Input id="location" {...register('personal.location')} placeholder="Rennes - mobile sur la France" />
            </Field>
            <Field label="LinkedIn" htmlFor="linkedin">
              <Input id="linkedin" {...register('personal.linkedin')} placeholder="linkedin.com/in/…" />
            </Field>
            <Field label="Portfolio / site" htmlFor="portfolio">
              <Input id="portfolio" {...register('personal.portfolio')} />
            </Field>
          </div>
          <Field label="Résumé professionnel" htmlFor="summary" hint="Base de l’accroche du CV ; l’IA la reformule pour chaque offre">
            <Textarea id="summary" rows={5} {...register('summary')} />
          </Field>
        </div>

        {/* ---------------- Expériences ---------------- */}
        <div className={section === 'experiences' ? 'space-y-4' : 'hidden'}>
          {experiences.fields.map((field, i) => (
            <fieldset key={field._key} className="rounded-lg border border-slate-200 p-4">
              <div className="mb-3 flex items-center justify-between">
                <legend className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                  <GripVertical className="h-4 w-4 text-slate-300" />
                  {form.watch(`experiences.${i}.role`) || 'Nouvelle expérience'}
                  <span className="font-mono text-[10px] font-normal text-slate-400">{field.id}</span>
                </legend>
                <Button type="button" variant="ghost" size="sm" className="text-red-600 hover:bg-red-50" onClick={() => experiences.remove(i)}>
                  <Trash2 /> Retirer
                </Button>
              </div>
              <input type="hidden" {...register(`experiences.${i}.id`)} />
              <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                <Field label="Poste">
                  <Input {...register(`experiences.${i}.role`, { required: true })} />
                </Field>
                <Field label="Entreprise">
                  <Input {...register(`experiences.${i}.company`, { required: true })} />
                </Field>
                <Field label="Client final" hint="Ex. mission en ESN">
                  <Input {...register(`experiences.${i}.client`)} />
                </Field>
                <Field label="Début" hint="AAAA-MM">
                  <Input {...register(`experiences.${i}.start_date`, { required: true })} placeholder="2024-09" />
                </Field>
                <Field label="Fin" hint="Vide = en cours">
                  <Input {...register(`experiences.${i}.end_date`)} placeholder="2026-08" />
                </Field>
                <Field label="Lieu">
                  <Input {...register(`experiences.${i}.location`)} />
                </Field>
                <Field label="Type de contrat">
                  <Input {...register(`experiences.${i}.contract_type`)} placeholder="CDI, Alternance, Stage…" />
                </Field>
              </div>
              <div className="mt-3 grid gap-3 lg:grid-cols-2">
                <Field label="Réalisations" hint="Une par ligne : l’IA en sélectionne et reformule pour chaque offre">
                  <Controller
                    control={control}
                    name={`experiences.${i}.achievements`}
                    render={({ field: f }) => <ListInput variant="lines" value={f.value ?? []} onChange={f.onChange} />}
                  />
                </Field>
                <Field label="Stack technique">
                  <Controller
                    control={control}
                    name={`experiences.${i}.skills`}
                    render={({ field: f }) => <ListInput value={f.value ?? []} onChange={f.onChange} />}
                  />
                </Field>
              </div>
              <Field label="Description (optionnelle)" className="mt-3">
                <Textarea rows={2} {...register(`experiences.${i}.description`)} />
              </Field>
            </fieldset>
          ))}
          <Button
            type="button"
            variant="outline"
            onClick={() =>
              experiences.append({ id: nextId('exp', experiences.fields), role: '', company: '', start_date: '', achievements: [], skills: [] })
            }
          >
            <Plus /> Ajouter une expérience
          </Button>
        </div>

        {/* ---------------- Projets ---------------- */}
        <div className={section === 'projects' ? 'space-y-4' : 'hidden'}>
          {projects.fields.map((field, i) => (
            <fieldset key={field._key} className="rounded-lg border border-slate-200 p-4">
              <div className="mb-3 flex items-center justify-between">
                <legend className="text-sm font-semibold text-slate-900">
                  {form.watch(`projects.${i}.name`) || 'Nouveau projet'}
                  <span className="ml-2 font-mono text-[10px] font-normal text-slate-400">{field.id}</span>
                </legend>
                <Button type="button" variant="ghost" size="sm" className="text-red-600 hover:bg-red-50" onClick={() => projects.remove(i)}>
                  <Trash2 /> Retirer
                </Button>
              </div>
              <input type="hidden" {...register(`projects.${i}.id`)} />
              <div className="grid gap-3 md:grid-cols-3">
                <Field label="Nom">
                  <Input {...register(`projects.${i}.name`, { required: true })} />
                </Field>
                <Field label="Type" hint="Académique, Personnel, Collaboratif…">
                  <Input {...register(`projects.${i}.kind`)} />
                </Field>
                <Field label="Statut" hint="Terminé, En cours…">
                  <Input {...register(`projects.${i}.status`)} />
                </Field>
              </div>
              <div className="mt-3 grid gap-3 lg:grid-cols-2">
                <Field label="Description">
                  <Textarea rows={3} {...register(`projects.${i}.description`)} />
                </Field>
                <Field label="Mission / rôle">
                  <Textarea rows={3} {...register(`projects.${i}.mission`)} />
                </Field>
              </div>
              <Field label="Technologies" className="mt-3">
                <Controller control={control} name={`projects.${i}.skills`} render={({ field: f }) => <ListInput value={f.value ?? []} onChange={f.onChange} />} />
              </Field>
            </fieldset>
          ))}
          <Button type="button" variant="outline" onClick={() => projects.append({ id: nextId('prj', projects.fields), name: '', skills: [] })}>
            <Plus /> Ajouter un projet
          </Button>
        </div>

        {/* ---------------- Compétences ---------------- */}
        <div className={section === 'skills' ? 'grid gap-5 md:grid-cols-2' : 'hidden'}>
          <SkillField control={control} name="skills.technical" label="Techniques" hint="Langages, frameworks, architectures" />
          <SkillField control={control} name="skills.tools" label="Outils" hint="CI/CD, cloud, bases de données, outillage" />
          <SkillField control={control} name="skills.business" label="Métier" hint="Domaines fonctionnels, méthodes" />
          <SkillField control={control} name="skills.soft_skills" label="Savoir-être" />
        </div>

        {/* ---------------- Formation & langues ---------------- */}
        <div className={section === 'education' ? 'space-y-5' : 'hidden'}>
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-slate-900">Formation</h3>
            {education.fields.map((field, i) => (
              <div key={field._key} className="grid gap-3 rounded-lg border border-slate-200 p-3 md:grid-cols-[1fr_1fr_1fr_6rem_6rem_auto]">
                <Field label="Diplôme">
                  <Input {...register(`education.${i}.degree`, { required: true })} />
                </Field>
                <Field label="Établissement">
                  <Input {...register(`education.${i}.institution`, { required: true })} />
                </Field>
                <Field label="Spécialité">
                  <Input {...register(`education.${i}.field_of_study`)} />
                </Field>
                <Field label="Début">
                  <Input {...register(`education.${i}.start_date`)} placeholder="2024" />
                </Field>
                <Field label="Fin">
                  <Input {...register(`education.${i}.end_date`)} placeholder="2026" />
                </Field>
                <Button type="button" variant="ghost" size="icon" className="mt-5 text-red-600 hover:bg-red-50" aria-label="Retirer" onClick={() => education.remove(i)}>
                  <Trash2 />
                </Button>
              </div>
            ))}
            <Button type="button" variant="outline" size="sm" onClick={() => education.append({ degree: '', institution: '' })}>
              <Plus /> Ajouter une formation
            </Button>
          </div>
          <div className="grid gap-5 md:grid-cols-2">
            <Field label="Langues" hint="Ex. « Anglais : professionnel »">
              <Controller control={control} name="languages" render={({ field: f }) => <ListInput value={f.value ?? []} onChange={f.onChange} />} />
            </Field>
            <Field label="Certifications">
              <Controller control={control} name="certifications" render={({ field: f }) => <ListInput value={f.value ?? []} onChange={f.onChange} />} />
            </Field>
          </div>
        </div>
      </div>
    </form>
  );
}

function SkillField({
  control,
  name,
  label,
  hint,
}: {
  control: Control<CandidateProfile>;
  name: 'skills.technical' | 'skills.tools' | 'skills.business' | 'skills.soft_skills';
  label: string;
  hint?: string;
}) {
  return (
    <Field label={label} hint={hint}>
      <Controller control={control} name={name} render={({ field: f }) => <ListInput value={f.value ?? []} onChange={f.onChange} />} />
    </Field>
  );
}

// Évite un avertissement "unused" tout en documentant le type attendu par register côté sections.
export type ProfileRegister = UseFormRegister<CandidateProfile>;
