import theano.tensor as tt
import theano
from .utils import variational_replacements, flatten
from .math import log_normal3


def sample_elbo(model, population=None, samples=1, pi=1):
    """ pi*KL[q(w|mu,rho)||p(w)] + E_q[log p(D|w)]
    approximated by montecarlo sampling

    Parameters
    ----------
    model : pmc3.Model
    population : dict - maps observed_RV to its population size
        if not provided defaults to full population
    samples : number of montecarlo samples used for approximation
    pi : additional coefficient for KL[q(w|mu,rho)||p(w)] as proposed in [1]_
    Returns
    -------
    elbo, updates, SharedADVIFit

    References
    ----------
    .. [1] Charles Blundell et al: "Weight Uncertainty in Neural Networks"
        arXiv preprint arXiv:1505.05424
    """
    if population is None:
        population = dict()
    replacements, _, shared = variational_replacements(model)
    x = flatten(replacements.values())
    mu = flatten(shared.means.values())
    rho = flatten(shared.rhos.values())

    def likelihood(var):
        tot = population.get(var, population.get(var.name))
        if tot is None:
            return tt.sum(var.logpt)
        else:
            return tt.sum(tot / var.size * var.logpt)

    log_p_D = tt.add(*map(likelihood, model.root.observed_RVs))
    log_p_W = model.root.varlogpt + tt.sum(model.root.potentials)
    log_q_W = tt.sum(log_normal3(x, mu, rho))
    _elbo_ = log_p_D + pi * (log_p_W - log_q_W)
    _elbo_ = theano.clone(_elbo_, replacements, strict=False)
    elbos, updates = theano.scan(fn=lambda: _elbo_,
                                 outputs_info=None,
                                 n_steps=samples)
    return tt.mean(elbos), updates, shared
