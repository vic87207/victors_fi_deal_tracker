# pylint: disable=too-many-ancestors, no-member
# ^ learned in class pylint probably can't see these
"""
Here is the main view module
We will create all the views for the website.
Took me a while to decide between class based with function based.
I think there were too many repetitive things the function based.
Plus I found the generic views that I think work better with class, and the Mixins too.
All the views should require login.
"""

import csv
from lib2to3.fixes.fix_input import context

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, FormView
from django.urls import reverse_lazy
from django.db.models import Sum, Count, Case, When, IntegerField
from django.http import HttpResponse
from .models import Deal
from .forms import DealForm, ReportForm


class DealListView(LoginRequiredMixin, ListView):
    """
    Here is the landing page. I want some most recent deals here. Ideally some graphs to summaraize
     deals.

    To-Do:
    1. need to fix the url for this one so we are not /deals all the time
    2. Graphs I want: PVR, PPD, current pay, forecast pay (forecast will be the hardest one I think)
    """
    model = Deal
    template_name = "deal_list.html"  # Remove 'deals/' prefix
    context_object_name = "deals"

    def get_queryset(self):
        """
        Let's just do the 5 most recent deals, maybe more in the future.
        """
        return Deal.objects.order_by('-deal_date')[:5]

class DealCreateView(LoginRequiredMixin, CreateView):
    """
    Here we create deals using CreateView, seems pretty easy
    """
    model = Deal
    form_class = DealForm
    template_name = "deal_form.html"  # Remove 'deals/' prefix
    success_url = reverse_lazy("deal-list")


class DealUpdateView(LoginRequiredMixin, UpdateView):
    """
    We edit deals from here, I should've probably called it update
    """
    model = Deal
    form_class = DealForm
    template_name = "deal_form.html"
    success_url = reverse_lazy("deal-list")


class DealDeleteView(LoginRequiredMixin, DeleteView):
    """
    Deleting deals from here.
    """
    model = Deal
    template_name = "deal_confirm_delete.html"
    success_url = reverse_lazy("deal-list")


class ReportView(LoginRequiredMixin, FormView):
    """
    We will be creating a report based on pvr, gross total, and other stats here.
    We will also be creating a csv out put from here to import to google sheets for management.
    We should be able to print out forms based on managers and date range.
    FormView is really great, practically built for this.
    """
    template_name = "report.html"
    form_class = ReportForm

    def form_valid(self, form):
        """
        here we use other functions to pull the data for the form
        """
        deals = self.get_filtered_deals(form)
        total_profit, total_deals, avg_profit_per_car = self.get_profit_summary(deals)
        products_sold, avg_products_sold = self.get_products_summary(deals)

        context = self.get_context_data(form=form)
        context.update({
            "total_profit": total_profit,
            "total_deals": total_deals,
            "avg_profit_per_car": avg_profit_per_car,
            "avg_products_sold": avg_products_sold,
            "products_sold": products_sold,
        })

        if "export_csv" in self.request.POST:
            return self.export_csv(deals)
        return self.render_to_response(context)

    def get_filtered_deals(self, form):
        """
        here we filter the deals by start/end date and managers who did the deal
        """
        deals = Deal.objects.all()
        start_date = form.cleaned_data["start_date"]
        end_date = form.cleaned_data["end_date"]
        managers = form.cleaned_data["managers"]

        if start_date:
            deals = deals.filter(deal_date__gte=start_date)
        if end_date:
            deals = deals.filter(deal_date__lte=end_date)
        if managers:
            deals = deals.filter(manager__in=managers)
        return deals

    def get_profit_summary(self, deals):
        """
        here we calculate the pvrs
        """
        profit_sum = deals.aggregate(
            total_profit=Sum("reserve")
            + Sum("vsc")
            + Sum("gap")
            + Sum("tw")
            + Sum("tricare")
            + Sum("key")
        )
        total_profit = profit_sum["total_profit"] or 0
        total_deals = deals.count()
        avg_profit_per_car = total_profit / total_deals if total_deals > 0 else 0

        return total_profit, total_deals, avg_profit_per_car

    def get_products_summary(self, deals):
        """
        here we calculate the ppd
        """
        products_sold = deals.aggregate(
            vsc_sold=Count(Case(When(vsc__gt=0, then=1), output_field=IntegerField())),
            gap_sold=Count(Case(When(gap__gt=0, then=1), output_field=IntegerField())),
            tw_sold=Count(Case(When(tw__gt=0, then=1), output_field=IntegerField())),
            tricare_sold=Count(
                Case(When(tricare__gt=0, then=1), output_field=IntegerField())
            ),
            key_sold=Count(Case(When(key__gt=0, then=1), output_field=IntegerField())),
        )

        total_deals = deals.count()
        avg_products_sold = (
            sum(products_sold.values()) / total_deals if total_deals > 0 else 0
        )
        return products_sold, avg_products_sold

    def export_csv(self, deals):
        """
        CSV export, so we can put this in google sheets where managers are comfortable
        """
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="deals_report.csv"'

        writer = csv.writer(response)
        # Took too long, stack overflow
        fields = [field.name for field in Deal._meta.get_fields() if hasattr(field, 'attname')]

        writer.writerow(fields)

        for deal in deals:
            writer.writerow([getattr(deal, field) for field in fields])

        return response
