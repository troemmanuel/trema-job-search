'use client';

import type { AiModel, CandidatePreferences } from '@trema/api-client';
import { Save } from 'lucide-react';
import { useEffect } from 'react';
import { Controller, useForm } from 'react-hook-form';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Field } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { ListInput } from '@/components/ui/list-input';
import { Select } from '@/components/ui/select';
import { SliderField } from '@/components/ui/slider-field';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';

interface PreferencesFormProps {
  preferences: CandidatePreferences;
  models: AiModel[];
  saving: boolean;
  onSave: (preferences: CandidatePreferences) => void;
}

export function PreferencesForm({ preferences, models, saving, onSave }: PreferencesFormProps) {
  const { control, register, handleSubmit, reset, watch, formState } = useForm<CandidatePreferences>({ defaultValues: preferences });
  useEffect(() => reset(preferences), [preferences, reset]);

  const priority = watch('match_threshold_priority') ?? 85;
  const recommended = watch('match_threshold_recommended') ?? 75;
  const review = watch('match_threshold_review') ?? 60;
  const thresholdsInvalid = !(priority > recommended && recommended > review);
  const currentModel = watch('ai_model');
  const knownModel = models.some((m) => m.id === currentModel);

  return (
    <form
      onSubmit={handleSubmit((values) =>
        onSave({
          ...values,
          minimum_salary: values.minimum_salary ? Number(values.minimum_salary) : null,
          daily_collection_limit: Number(values.daily_collection_limit),
        }),
      )}
      className="space-y-6"
    >
      <div className="sticky top-16 z-[5] -mx-8 flex items-center justify-end gap-3 border-b border-slate-200 bg-white/80 px-8 py-2 backdrop-blur">
        {formState.isDirty ? <span className="text-xs text-amber-600">Modifications non enregistrées</span> : null}
        {thresholdsInvalid ? <span className="text-xs text-red-600">Les seuils doivent être décroissants : prioritaire &gt; recommandé &gt; à revoir</span> : null}
        <Button type="submit" size="sm" loading={saving} disabled={!formState.isDirty || thresholdsInvalid}>
          <Save /> Enregistrer les paramètres
        </Button>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        {/* Critères de recherche */}
        <Card>
          <CardHeader>
            <CardTitle>Critères de recherche</CardTitle>
            <CardDescription>Guident la collecte automatique et le scoring de chaque offre</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field label="Intitulés de poste ciblés" hint="Utilisés comme requêtes de collecte et pour le matching du titre">
              <Controller control={control} name="target_titles" render={({ field }) => <ListInput value={field.value ?? []} onChange={field.onChange} />} />
            </Field>
            <Field label="Localisations" hint="Villes, régions, « France entière »">
              <Controller control={control} name="locations" render={({ field }) => <ListInput value={field.value ?? []} onChange={field.onChange} />} />
            </Field>
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Types de contrat">
                <Controller control={control} name="contract_types" render={({ field }) => <ListInput value={field.value ?? []} onChange={field.onChange} placeholder="CDI, CDD, Freelance…" />} />
              </Field>
              <Field label="Salaire minimum (€ brut / an)" hint="Vide = pas de plancher">
                <Input type="number" step={1000} {...register('minimum_salary')} placeholder="45000" />
              </Field>
            </div>
            <Field label="Secteurs privilégiés">
              <Controller control={control} name="sectors" render={({ field }) => <ListInput value={field.value ?? []} onChange={field.onChange} placeholder="Fintech, Santé, Énergie…" />} />
            </Field>
            <Controller
              control={control}
              name="remote"
              render={({ field }) => <Switch checked={field.value ?? false} onCheckedChange={field.onChange} label="Ouvert au télétravail" description="Pondère la dimension localisation du matching" />}
            />
          </CardContent>
        </Card>

        {/* Filtres */}
        <Card>
          <CardHeader>
            <CardTitle>Filtres de pré-tri</CardTitle>
            <CardDescription>Écartent les offres avant tout appel à l’IA (économie de quota)</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field label="Entreprises exclues" hint="Leurs offres sont ignorées par la collecte. Depuis une fiche offre, « Exclure » marque aussi les offres déjà collectées.">
              <Controller control={control} name="excluded_companies" render={({ field }) => <ListInput value={field.value ?? []} onChange={field.onChange} placeholder="Capgemini, Alten…" />} />
            </Field>
            <Field label="Mots-clés indésirables" hint="Présents dans le titre → offre écartée">
              <Controller control={control} name="excluded_keywords" render={({ field }) => <ListInput value={field.value ?? []} onChange={field.onChange} placeholder="Stage, PHP, Manager…" />} />
            </Field>
            <Controller
              control={control}
              name="filter_esn"
              render={({ field }) => <Switch checked={field.value ?? false} onCheckedChange={field.onChange} label="Filtrer les ESN / sociétés de conseil" description="Les entreprises identifiées comme ESN sont écartées automatiquement" />}
            />
          </CardContent>
        </Card>

        {/* Seuils */}
        <Card>
          <CardHeader>
            <CardTitle>Seuils de scoring</CardTitle>
            <CardDescription>Classent chaque offre selon son score de matching sur 100</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Controller control={control} name="match_threshold_priority" render={({ field }) => <SliderField label="Prioritaire" hint="Match idéal : à traiter en premier" min={70} max={95} value={field.value ?? 85} onChange={field.onChange} format={(v) => `≥ ${v}`} />} />
            <Controller control={control} name="match_threshold_recommended" render={({ field }) => <SliderField label="Recommandée" hint="Qualification automatique et préparation du dossier" min={60} max={90} value={field.value ?? 75} onChange={field.onChange} format={(v) => `≥ ${v}`} />} />
            <Controller control={control} name="match_threshold_review" render={({ field }) => <SliderField label="À revoir" hint="En dessous : ignorée automatiquement" min={40} max={75} value={field.value ?? 60} onChange={field.onChange} format={(v) => `≥ ${v}`} />} />
          </CardContent>
        </Card>

        {/* IA */}
        <Card>
          <CardHeader>
            <CardTitle>Modèle & rédaction IA</CardTitle>
            <CardDescription>Modèle Gemini principal et style des documents générés</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field label="Modèle par défaut" hint={!knownModel && currentModel ? `« ${currentModel} » n’est pas dans la liste proposée : conservé tel quel.` : undefined}>
              <Select {...register('ai_model')}>
                {!knownModel && currentModel ? <option value={currentModel}>{currentModel} (actuel)</option> : null}
                {models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                    {m.recommended ? ' · recommandé' : ''}
                  </option>
                ))}
              </Select>
            </Field>
            <Controller
              control={control}
              name="ai_temperature"
              render={({ field }) => <SliderField label="Température" hint="0 = déterministe, 1 = créatif ; 0.2 recommandé pour des documents sobres" min={0} max={1} step={0.05} value={field.value ?? 0.2} onChange={field.onChange} format={(v) => v.toFixed(2)} />}
            />
            <Field label="Instructions personnalisées" hint="Ajoutées à chaque prompt de génération (ton, éléments à mettre en avant, interdits…)">
              <Textarea rows={4} {...register('ai_custom_instructions')} placeholder="Ex. : privilégier les réalisations chiffrées, ne jamais mentionner…" />
            </Field>
          </CardContent>
        </Card>

        {/* Automatisation */}
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle>Automatisation</CardTitle>
            <CardDescription>Comportement de la collecte quotidienne et des imports</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            <Controller
              control={control}
              name="auto_prepare_documents"
              render={({ field }) => <Switch checked={field.value ?? false} onCheckedChange={field.onChange} label="Préparer automatiquement les dossiers" description="CV, lettre et réponses générés dès qu’une offre atteint le seuil recommandé" />}
            />
            <Controller
              control={control}
              name="auto_sync_notion"
              render={({ field }) => <Switch checked={field.value ?? false} onCheckedChange={field.onChange} label="Synchroniser Notion automatiquement" description="Crée / met à jour la fiche CRM à chaque dossier préparé" />}
            />
            <Field label="Période de collecte par défaut">
              <Select {...register('default_search_duration')}>
                <option value="24h">Dernières 24 h</option>
                <option value="3j">3 derniers jours</option>
                <option value="7j">7 derniers jours</option>
              </Select>
            </Field>
            <Field label="Offres maximum par collecte" hint="Limite le nombre d’offres analysées par passage (quota IA)">
              <Input type="number" min={1} max={20} {...register('daily_collection_limit')} />
            </Field>
          </CardContent>
        </Card>
      </div>
    </form>
  );
}
